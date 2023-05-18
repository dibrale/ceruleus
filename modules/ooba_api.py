from modules.logutils import print_v
from modules.tokenutils import llama_token_length

import websockets
import json
import asyncio
import sys


# Sends aggregated text to the large language model's API
# TODO: Un-hardcode parameters
async def send_to_llm(aggregated_text: str, loop: asyncio.AbstractEventLoop):
    host = 'localhost:5005'
    uri = f'ws://{host}/api/v1/stream'

    request = {
        'prompt': aggregated_text,
        'max_new_tokens': 200,
        'do_sample': True,
        'temperature': 0.7,
        'top_p': 0.5,
        'typical_p': 0.6,
        'repetition_penalty': 1.18,
        'encoder_repetition_penalty': 1.05,
        'top_k': 15,
        'min_length': 0,
        'no_repeat_ngram_size': 0,
        'num_beams': 1,
        'penalty_alpha': 2.5,
        'length_penalty': 1,
        'early_stopping': False,
        'seed': -1,
        'add_bos_token': False,
        'truncation_length': 1800,
        'ban_eos_token': False,
        'skip_special_tokens': True,
        'stopping_strings': ['[END]', 'end(code)']
    }

    async with websockets.connect(uri, ping_interval=15, ping_timeout=60) as websocket:
        print_v(f'Sending request to {host}')
        await websocket.send(json.dumps(request))
        print_v(f'Awaiting response')

        while True:
            try:
                incoming_data = await websocket.recv()
            except websockets.ConnectionClosed:

                yield "\nConnection lost\n"
                return

            execute_load = loop.run_in_executor(None, json.loads, incoming_data)
            loaded_data = await execute_load

            match loaded_data['event']:
                case 'text_stream':
                    yield loaded_data['text']
                case 'stream_end':
                    print()
                    return


async def print_response_stream(prompt, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop) -> bool:
    response_final = ''
    async for response in send_to_llm(prompt, loop):
        print(response, end='')
        response_final += response
        await loop.run_in_executor(None, sys.stdout.flush)  # If we don't flush, we won't see tokens in realtime.
    await queue.put(response_final)
    return True


# Just print out the prompt you would send for debugging
def dummy_send_to_llm(aggregated_text: str):
    print(aggregated_text)
    print(f"Tokens: {llama_token_length(aggregated_text)}")
