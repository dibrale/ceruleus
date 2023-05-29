import asyncio
from asyncio import AbstractEventLoop
from subprocess import PIPE, STDOUT
from datetime import timedelta, datetime
from watchdog.observers import Observer

from watchdog.events import FileSystemEventHandler

from modules.config import params, path
from modules.logutils import print_v
from modules.rwutils import read_text_file, write_json_data, write_text_file
from modules.saveutils import parse_save_answer


# Custom event handler class that triggers when a new file is created
class NewFileHandler(FileSystemEventHandler):
    def __init__(self, file_queue: asyncio.Queue, text_queue: asyncio.Queue, loop: AbstractEventLoop):
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

        if event.src_path.endswith('.txt'):
            print_v('Text file modified: ' + event.src_path)
            content = await read_text_file(event.src_path)
            answer_task = parse_save_answer(content, self.loop)
            text_queue_task = self.text_queue.put(content + '\n')
            await asyncio.gather(answer_task, text_queue_task)

    # Synchronous wrapper for on_created_async
    def on_any_event(self, event):
        self.loop.create_task(self._on_any_event_async(event))


# Monitors a directory for new text files and triggers the event handler
async def monitor_directory(
        dir_path: str,
        file_queue: asyncio.Queue,
        text_queue: asyncio.Queue,
        loop: AbstractEventLoop):
    print_v(f"Monitoring {dir_path} directory")

    # Monitoring is accomplished using a listener
    event_handler = NewFileHandler(file_queue, text_queue, loop)
    observer = Observer()
    observer.schedule(event_handler, dir_path, recursive=False)
    observer.start()

    try:
        while True:
            await asyncio.sleep(0.25)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()


async def run_script(script_path, *args, interpreter="python", prefix=''):
    if prefix:
        prefix += ' '
    command = f"{prefix}{interpreter} {script_path} " + ' '.join(args)
    print_v(f"Running command: {command}")
    subprocess = await asyncio.create_subprocess_shell(command, stdin=PIPE, stdout=PIPE, stderr=STDOUT)

    async def read_stream(stream):
        while True:
            line = await stream.readline()
            if not line:
                break
            print(line.decode().rstrip())

    await read_stream(subprocess.stdout)
    await subprocess.wait()

    if subprocess.returncode != 0:
        print_v(f'Process exited with {subprocess.returncode}')
    else:
        print_v('Process completed successfully', params['verbose'])

    return subprocess.returncode


# Initialize the work files and clear the Squire question file
async def reset(loop: AbstractEventLoop) -> bool:
    print_v("Initializing the work files")
    clear_answers_task = loop.create_task(write_json_data({'answers': []}, path['answers']))
    clear_thoughts_task = loop.create_task(write_json_data({'thoughts': []}, path['thoughts']))
    clear_goals_task = loop.create_task(write_json_data({'goals': []}, path['goals']))
    clear_question = loop.create_task(write_text_file('', path['squire_question']))
    await asyncio.gather(clear_answers_task, clear_thoughts_task, clear_goals_task, clear_question)
    return True
