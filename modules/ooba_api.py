from modules.api import signal
from modules.config import params, webui_params
from modules.logutils import print_v
from modules.tokenutils import llama_token_length

import websockets
import json
import asyncio
import sys


# Sends aggregated text to the large language model's API
async def send_to_llm(aggregated_text: str, loop: asyncio.AbstractEventLoop):
    host = 'localhost:5005'
    uri = f'ws://{host}/api/v1/stream'

    request = {'prompt': aggregated_text, **webui_params}

    async with websockets.connect(
            uri,
            ping_interval=params['ping_interval'],
            ping_timeout=params['ping_timeout']
    ) as websocket:
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
    await signal('webui')
    response_final = ''
    async for response in send_to_llm(prompt, loop):
        print(response, end='')
        response_final += response
        await loop.run_in_executor(None, sys.stdout.flush)  # If we don't flush, we won't see tokens in realtime.
    await queue.put(response_final)
    return True


# Just print out the prompt you would send for debugging
def dummy_send_to_webui(aggregated_text: str):
    print(aggregated_text)
    print(f"Tokens: {llama_token_length(aggregated_text)}")
