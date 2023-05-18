from modules.rwutils import *
import re


# Parse thoughts from an arbitrary string and save them to the thoughts JSON, optionally also to the persistent dialogue
async def save_thought(input_string: str):
    # Extract the text between 'Thought: ' and 'Question:'
    result = re.search(r"Thoughts*?\s*\d*\s*:\s*\d*\s*(?P<THOUGHT>(.*?))\n*\s*\d*Question", input_string)

    try:
        thought = result.group('THOUGHT')
        print_v(f'Thought: {thought}', params['verbose'])
    except AttributeError:
        print_v(f'No thought to write', params['verbose'])
        return

    # Append the extracted thought to the "thoughts" list
    thoughts_data = await load_json_data(f"{params['results_dir']}/thoughts.json")
    try:
        thoughts_data['thoughts'].index(thought)
        print_v(f'Thought already exists in thoughts.json', params['verbose'])
    except ValueError:
        thoughts_data['thoughts'].append(thought)
        await write_json_data(thoughts_data, f"{params['results_dir']}/thoughts.json")

        # Prepare thought string for chat history
        thought_bubble = f"*{attributes['char_name']} thinks to herself: {thought}*"

        # Load chat history and write to it
        convo_data_full = await load_json_data(params['char_log_path'])
        convo_data_full['data'].append(['', thought_bubble])
        if params['telesend']:
            convo_data_full['data_visible'].append(['', thought_bubble])
        await write_json_data(convo_data_full, params['char_log_path'])
    finally:
        return


# Take a string and save it in the answers JSON
async def save_answer(input_string: str):
    input_string = input_string.strip()

    # Append the extracted thought to the "thoughts" list
    answers_data = await load_json_data(f"{params['results_dir']}/answers.json")
    try:
        answers_data['answers'].index(input_string.strip())
        print_v(f'Answer already exists in answers.json', params['verbose'])
    except ValueError:
        answers_data['answers'].append(input_string)
        await write_json_data(answers_data, f"{params['results_dir']}/answers.json")
    finally:
        return


# Parse a goal out of an arbitrary string and save it in the goals JSON
async def save_goal(input_string: str):
    # Extract the text 'Goal: ' and a period'
    result = re.search(r"Goals?\s*\d*\s*:\s*\d*\s*(?P<GOAL>(.*?)\.)", input_string)

    try:
        goal = result.group('GOAL')
        print_v(f'Goal: {goal}', params['verbose'])
    except AttributeError:
        print_v("No goal to write")
        return

    # Append the extracted goal to the "goals" list
    goals_data = await load_json_data(f"{params['results_dir']}/goals.json")

    try:
        goals_data['goals'].index(goal)
        print_v(f'Goal already exists in goals.json', params['verbose'])
    except ValueError:
        goals_data['goals'].append(goal)
        await write_json_data(goals_data, f"{params['results_dir']}/goals.json")

        # Prepare goal string for chat history
        thought_bubble = f"*{attributes['char_name']} has a goal: {goal}*"

        # Load chat history and write to it
        convo_data_full = await load_json_data(params['char_log_path'])
        convo_data_full['data'].append(['', thought_bubble])
        if params['telesend']:
            convo_data_full['data_visible'].append(['', thought_bubble])
        await write_json_data(convo_data_full, params['char_log_path'])
    finally:
        return


# Write speech to the chat log
async def save_speech(input_string: str):
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
    speech = re.findall(r".*[.!?*~]", speech.strip('\"'))[0]
    speech_test = speech.strip().strip('.?!~*:').lower()

    if speech_test.startswith('no') and (speech_test.endswith('at this time') or speech_test.endswith('speech')):
        print_v("No new speech", params['verbose'])
        return

    # Load chat history
    convo_data_full = await load_json_data(params['char_log_path'])

    # Process speech text and escape in case of duplication
    if convo_data_full['data'][-1][-1] == speech or convo_data_full['data_visible'][-1][-1] == speech:
        print_v("Duplicate speech suppressed", params['verbose'])
        return

    # Write chat history
    convo_data_full['data'].append(['', speech])
    convo_data_full['data_visible'].append(['', speech])
    print_v("Writing speech to persistent JSON", params['verbose'])
    await write_json_data(convo_data_full, params['char_log_path'])
    print_v("New speech written")
    return
