import asyncio
from pathlib import Path

from datetime import timedelta
from shutil import copyfile
from subprocess import PIPE, STDOUT

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from modules.logutils import *
from modules.ooba_api import print_response_stream
from modules.saveutils import *
from modules.tokenutils import *
from modules.stringutils import *

from modules.config import params, attributes

# TODO: Argparse


# Custom event handler class that triggers when a new file is created
class NewFileHandler(FileSystemEventHandler):
    def __init__(self, file_queue, text_queue):
        self.loop = loop
        self.queue = file_queue
        self.text_queue = text_queue
        self.last_modified = datetime.now()

    # Asynchronously called when a new file is detected
    async def _on_any_event_async(self, event):

        delta = datetime.now() - self.last_modified
        if datetime.now() - self.last_modified < timedelta(seconds=1):
            print_v(f"Additional event detected, but suppressed: {event.src_path}", params['verbose'])
            print_v(f"Time since prior event: {round(delta.microseconds / 1000)} ms", params['verbose'])
            return
        else:
            self.last_modified = datetime.now()

        await asyncio.sleep(0)
        if event.src_path.endswith('.txt'):
            print_v('Text file modified: ' + event.src_path)
            path.update({'squire_out': event.src_path})
            content = await read_text_file(event.src_path)
            await save_answer(content)
            await self.text_queue.put(content + '\n')

    # Synchronous wrapper for on_created_async
    def on_any_event(self, event):
        self.loop.create_task(self._on_any_event_async(event))


# Monitors a directory for new text files and triggers the event handler
async def monitor_directory(dir_path: str, file_queue: asyncio.Queue, text_queue: asyncio.Queue):
    print_v(f"Monitoring {params['squire_out_dir']} directory")

    # Monitoring is accomplished using a listener
    event_handler = NewFileHandler(file_queue, text_queue)
    observer = Observer()
    observer.schedule(event_handler, dir_path, recursive=False)
    observer.start()

    try:
        while True:
            await asyncio.sleep(0.25)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()


# Aggregates text content from the queue
async def aggregate_text(statement, text, body, chara_text, thoughts, answers, convo):
    print_v("Aggregator waiting for text", params['verbose'])

    # Make timestamp
    time_stamp = f"\nCurrent Date: {next(long_date())}\nCurrent Local Time: {next(time())}"

    aggregated_text = '\nAnswer: '

    # Asynchronously get text from Squire
    aggregated_text += text
    print_v(f'Aggregator found new output', params['verbose'])

    # Format character text using the template
    chara_text = chara_text.format(
        persona=attributes['char_persona'].strip(),
        scenario=attributes['world_scenario'].strip(),
    )

    # Tasks to process answers, thoughts and conversation into strings
    answer_loader = loop.create_task(make_answers_string(answers, 400))
    thought_loader = loop.create_task(make_thoughts_string(thoughts, 300))
    statement_loader = loop.create_task(last_statement_thought(convo, statement))
    convo_loader = loop.create_task(make_convo_string(convo, 300))

    # Gather answers, thoughts and conversation text before moving on
    answer_text, thought_text, statement_text, convo_text = await asyncio.gather(
        answer_loader, thought_loader, statement_loader, convo_loader)

    print_v('Preparing final prompt', params['verbose'])
    final_prompt = llama_squeeze(
        chara_text + convo_text + time_stamp
        + thought_text + statement_text
        + answer_text
        + aggregated_text
        + body + '\n')  # Llama gives null output when prompt does not end with newline

    print_v('Generated prompt', params['verbose'])
    print_v(f'Approximate length: {llama_token_length(final_prompt)} tokens', params['verbose'])
    return final_prompt


# Function to handle rx/tx to the user-facing LLM
async def exchange(
        aggregated_queue: asyncio.Queue,
        response_queue: asyncio.Queue,
        squire_queue: asyncio.Queue,
        retry_delay=params['retry_delay']
):
    aggregated_text = await aggregated_queue.get()
    response_done = False
    while not response_done:
        try:
            response_done = await print_response_stream(assure_string(aggregated_text), response_queue, loop)
        except ConnectionError as e:
            print_v(e)
            print_v(f'Waiting for {retry_delay} seconds, then trying again')
            await asyncio.sleep(retry_delay)
    response = await response_queue.get()

    if response:
        gathered_question = await asyncio.gather(
            parse_question(response),
            save_thought(response),
            save_goal(response),
            save_speech(response)
        )
        parsed_question = assure_string(gathered_question[0])

        await squire_queue.put(parsed_question)


async def run_script(script_path, *args, interpreter="python", prefix=''):
    if prefix:
        prefix += ' '
    command = f"{prefix}{interpreter} {script_path} " + ' '.join(args)
    print_v(f"Running command: {command}")
    process = await asyncio.create_subprocess_shell(command, stdin=PIPE, stdout=PIPE, stderr=STDOUT)

    async def read_stream(stream):
        while True:
            line = await stream.readline()
            if not line:
                break
            print(line.decode().rstrip())

    await asyncio.gather(read_stream(process.stdout))
    await process.wait()

    if process.returncode != 0:
        print_v(f'Process exited with {process.returncode}')
    else:
        print_v('Process completed successfully', params['verbose'])

    return process.returncode


async def send_to_squire(in_queue: asyncio.Queue):
    text = await in_queue.get()
    if text == '' or not text:
        print_v('Continuing without asking a question - writing loopback reply')
        await loop.run_in_executor(None, copyfile, path['continue_template'], path['squire_out'])

    else:
        print_v('Got question text. Preparing to write question.txt', params['verbose'])
        await write_text_file(text, path['squire_question'])

        # Pass the CUDA_VISIBLE_DEVICES parameter when running Squire
        if params['CUDA_VISIBLE_DEVICES']:
            prefix = f"CUDA_VISIBLE_DEVICES={params['CUDA_VISIBLE_DEVICES']}"
        else:
            prefix = ''

        args = (
            '-o', path['squire_out'],
            '-l', path['squire_model'],
            '-m', path['squire_template'],
            '-q', path['squire_question']
        )

        code = await run_script(path['squire'], *args, prefix=prefix)

        # Handle Squire failing by writing an output file communicating that
        if code != 0:
            await write_text_file(
                'Could not return an answer. Try rephrasing your question and asking again.',
                path['squire_out']
            )
    await asyncio.sleep(0)


# Main function that runs the script
async def main():

    # Using lots of different queues to avoid accidental ingestion
    file_queue = asyncio.Queue()
    text_queue = asyncio.Queue()
    squire_queue = asyncio.Queue()
    response_queue = asyncio.Queue()
    aggregate_queue = asyncio.Queue()

    # Monitor the directory for new text files
    asyncio.run_coroutine_threadsafe(monitor_directory(params['squire_out_dir'], file_queue, text_queue), loop)

    while True:
        # Task to continuously send text to the LLM
        exchange_task = loop.create_task(exchange(aggregate_queue, response_queue, squire_queue))

        # Task to launch Squire in response to a question by the LLM
        squire_task = loop.create_task(send_to_squire(squire_queue))

        # Load all data needed to generate a prompt. Should be rate-limited by text_queue.get()
        text, statement, body, chara_text, thoughts, answers, convo = await asyncio.gather(
            text_queue.get(),
            read_text_file(path['statement_template']),
            read_text_file(path['body_template']),
            read_text_file(path['char_template']),
            load_json_data(path['thoughts']),
            load_json_data(path['answers']),
            load_json_data(path['char_log'])
        )

        # Generate the prompt
        aggregate_task = loop.create_task(aggregate_text(statement, text, body, chara_text, thoughts, answers, convo))
        prompt = await aggregate_task

        # Await tasks for getting the prompt, processing it, then sending the reply to Squire
        put_task = aggregate_queue.put(prompt)
        await put_task
        await exchange_task
        await squire_task


if __name__ == "__main__":
    # Create file paths
    path = {
        'statement_template': f"{params['template_dir']}/statement_template.txt",
        'body_template': f"{params['template_dir']}/body_template.txt",
        'char_template': f"{params['template_dir']}/character_template.txt",
        'continue_template': f"{params['template_dir']}/continue_template.txt",
        'char_card': params['char_card_path'],
        'thoughts': f"{params['results_dir']}/thoughts.json",
        'goals': f"{params['results_dir']}/thoughts.json",
        'answers': f"{params['results_dir']}/answers.json",
        'char_log': params['char_log_path'],
        'squire': f"{params['squire_path']}/squire.py",
        'squire_template': f"{params['squire_path']}/template.txt",
        'squire_question': f"{params['squire_path']}/question.txt",
        'squire_model': params['squire_model_path']
    }

    # Check file paths before entering loop
    paths_found = 0
    for key in path.keys():
        if key:
            f = Path(path[key])
            if f.is_file():
                print_v(f"Found {path[key]}", params['verbose'])
                paths_found += 1
            elif f.is_dir():
                print_v(f"{path[key]} is a directory. Expected a file.")
            elif not f.exists():
                print_v(f"{path[key]} not found.")
    print_v(f"Found {paths_found}/{len(path)} input files")
    if paths_found != len(path):
        raise FileNotFoundError("Some required input files could not be found. See output for details. Check your "
                                "parameters and ensure the files are in place.")

    path.update({'squire_out': f"{params['squire_out_dir']}/out.txt"})

    # Enter the main event loop
    loop = asyncio.get_event_loop()
    asyncio.ensure_future(main())
    loop.run_forever()
