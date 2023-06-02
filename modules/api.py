import functools
from asyncio import AbstractEventLoop

from websockets.exceptions import ConnectionClosed
from websockets.legacy.server import WebSocketServerProtocol

from modules.config import params
from modules.logutils import print_v

import asyncio
import websockets.server
import json

# Make the API semaphore
semaphore = {
    'pause': False,
    'webui': True,
    'squire': True
}


async def receive_data(websocket: WebSocketServerProtocol, receive_queue: asyncio.Queue):
    try:
        json_data = await websocket.recv()
        data = json.loads(json_data)
        print_v(f"Received {type(data)} from websocket", params['verbose'])
        await receive_queue.put(data)
    except ConnectionClosed as e:
        print_v(e)
    await asyncio.sleep(0)


async def send_data(websocket: WebSocketServerProtocol, send_queue: asyncio.Queue):
    out = await send_queue.get()
    print_v(f"Sending {str(out)} to websocket", params['verbose'])
    try:
        await websocket.send(json.dumps(out))
    except ConnectionClosed as e:
        print_v(e)
        # Replace the outgoing message in the queue if it could not be sent
        await send_queue.put(out)
    await asyncio.sleep(0)


# Websockets handler
async def handler(
        websocket,
        send_queue: asyncio.Queue,
        receive_queue: asyncio.Queue,
        loop: AbstractEventLoop):
    receiver_task = loop.create_task(receive_data(websocket, receive_queue))
    sender_task = loop.create_task(send_data(websocket, send_queue))
    done, pending = await asyncio.wait([receiver_task, sender_task], return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    await asyncio.sleep(0)


async def start_server(
        send_queue: asyncio.Queue,
        receive_queue: asyncio.Queue,
        loop: AbstractEventLoop,
        host="localhost",
        port=1230):
    print_v(f"Starting server at {host}:{port}")

    queued_handler = functools.partial(handler, send_queue=send_queue, receive_queue=receive_queue, loop=loop)
    stop = asyncio.Future()
    async with websockets.server.serve(queued_handler, host, port):
        await stop


# Fake signal manager for testing. Just prints the signal and does nothing
async def fake_signal_manager(receive_queue: asyncio.Queue):
    while True:
        item = await receive_queue.get()
        print(f"Got signal type {type(item)} from queue\nContents: {str(item)}")
        await asyncio.sleep(0)


# The actual signal manager. Updates the internal semaphore
async def signal_manager(receive_queue: asyncio.Queue):
    while True:
        item = await receive_queue.get()
        print_v(f"Got signal type {type(item)} from queue\nContents: {str(item)}", params['verbose'])
        for key in item.keys():
            semaphore.update({key: item[key]})
        await asyncio.sleep(0)


# Get a semaphore signal
async def get_signal(key):
    try:
        return semaphore[key]
    except KeyError:
        return None


# Wait at the semaphore
async def signal(key, go_value=True, go_on_none=False, check_frequency=0.25):
    print_v(f"Waiting at semaphore for {key}:{go_value}", params['verbose'])
    while True:
        sig = await get_signal(key)
        if sig == go_value:
            break
        elif isinstance(sig, type(None)) and go_on_none:
            break
        await asyncio.sleep(check_frequency)
    print_v(f"Semaphore cleared with {key}:{sig}", params['verbose'])
