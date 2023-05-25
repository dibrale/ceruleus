import asyncio
from asyncio import AbstractEventLoop

from modules.rwutils import *
import re


# Parse thoughts from an arbitrary string and save them to the thoughts JSON, optionally also to the persistent dialogue
async def parse_save_thought(input_string: str, loop: AbstractEventLoop):
    # Extract the text between 'Thought: ' and 'Question:'
    result = re.search(r"Thoughts*?\s*\d*\s*:\s*\d*\s*(?P<THOUGHT>(.*?))\n*\s*\d*Question", input_string)

    try:
        thought = result.group('THOUGHT')
        print_v(f'Thought: {thought}', params['verbose'])
    except AttributeError:
        print_v(f'No thought to write', params['verbose'])
        return

    # Append the extracted thought to the "thoughts" list
    thoughts_data = await load_json_data(path['thoughts'])
    try:
        thoughts_data['thoughts'].index(thought)
        print_v(f'Thought already exists in thoughts.json', params['verbose'])
    except ValueError:
        thoughts_data['thoughts'].append(thought)

        write_work_task = loop.create_task(write_json_data(thoughts_data, path['thoughts']))
        append_result_task = loop.create_task(append_json_data(thought, 'thoughts', path['thoughts_persistent']))

        # Prepare goal prefix for chat history, then load chat history and write to it
        write_crumb_task = write_crumb(thought, prefix=f"{attributes['char_name']} thinks: ")

        await asyncio.gather(write_work_task, append_result_task, write_crumb_task)
    finally:
        return


# Take a string and save it in the answers JSON
async def parse_save_answer(input_string: str, loop: AbstractEventLoop):
    input_string = input_string.strip()

    # Append the extracted thought to the "thoughts" list
    answers_data = await load_json_data(path['answers'])
    try:
        answers_data['answers'].index(input_string.strip())
        print_v(f'Answer already exists in answers.json', params['verbose'])
    except ValueError:
        answers_data['answers'].append(input_string)
        write_work = loop.create_task(write_json_data(answers_data, path['answers']))
        append_persistent = loop.create_task(append_json_data(input_string, 'answers', path['answers_persistent']))
        await asyncio.gather(write_work, append_persistent)
    finally:
        return


# Parse a goal out of an arbitrary string and save it in the goals JSON
async def parse_save_goal(input_string: str, loop: AbstractEventLoop):
    # Extract the text 'Goal: ' and a period'
    result = re.search(r"Goals?\s*\d*\s*:\s*\d*\s*(?P<GOAL>(.*?)\.)", input_string)

    try:
        goal = result.group('GOAL')
        print_v(f'Goal: {goal}', params['verbose'])
    except AttributeError:
        print_v("No goal to write")
        return

    # Append the extracted goal to the "goals" list
    goals_data = await load_json_data(path['goals'])

    try:
        goals_data['goals'].index(goal)
        print_v(f'Goal already exists in goals.json', params['verbose'])
    except ValueError:
        goals_data['goals'].append(goal)

        write_work_task = loop.create_task(write_json_data(goals_data, path['goals']))
        append_result_task = loop.create_task(append_json_data(goals_data, 'goals', path['goals_persistent']))

        # Prepare goal prefix for chat history, then load chat history and write to it
        write_crumb_task = write_crumb(goal, prefix=f"{attributes['char_name']} has a goal: ")

        await asyncio.gather(write_work_task, append_result_task, write_crumb_task)
    finally:
        return


# Write speech to the chat log
async def parse_save_speech(input_string: str):
    # Extract the text after 'Speech: '
    result = re.search(
        r"(Speech|{name})\s*\d*\s*:\s*\d*\s*({name}\s*\d*\s*:\s*\d*\s*)*(?P<SPEECH>(.*?)$)"
        .format(name=attributes['char_name']), input_string)

    try:
        speech = result.group('SPEECH')
    except AttributeError:
        print_v("No speech to write", params['verbose'])
        return

    # Remove incomplete sentences from speech to be written
    try:
        speech = re.findall(r".*[.!?*~]", speech.strip('\"'))[0]
    except IndexError:
        print_v("No new speech", params['verbose'])
        return

    speech_test = speech.strip().strip('.?!~*:').lower()
    if speech_test.startswith('no') and (
            speech_test.endswith('at this time') or
            speech_test.endswith('speech') or
            speech_test.endswith('at present') or
            speech_test.endswith('presently') or
            speech_test.endswith('now') or
            speech_test.endswith('yet')
    ):
        print_v("No new speech", params['verbose'])
        return

    # Load chat history
    convo_data_full = await load_json_data(path['char_log'])

    # Process speech text and escape in case of duplication
    if convo_data_full['data'][-1][-1] == speech or convo_data_full['data_visible'][-1][-1] == speech:
        print_v("Duplicate speech suppressed", params['verbose'])
        return

    # Write chat history
    convo_data_full['data'].append(['', speech])
    convo_data_full['data_visible'].append(['', speech])
    print_v("Writing speech to persistent JSON", params['verbose'])
    await write_json_data(convo_data_full, path['char_log'])
    print_v("New speech written")
    return


# Write crumbs of knowledge to the conversation log
async def write_crumb(crumb: str, prefix='I gained some new knowledge: '):
    convo_data_full = await load_json_data(params['char_log_path'])
    convo_data_full['data'].append(['', prefix + crumb])
    if params['telesend']:
        convo_data_full['data_visible'].append(['', prefix + crumb])
    await write_json_data(convo_data_full, params['char_log_path'])
    return
