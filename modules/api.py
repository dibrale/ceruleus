import functools
from typing import Awaitable, Callable

from websockets.exceptions import ConnectionClosed
from websockets.legacy.client import WebSocketClientProtocol
from websockets.legacy.server import WebSocketServerProtocol

from modules.config import send_queue, receive_queue
from modules.logutils import print_v, get_fcn_name, log_timestamp
from modules.sigutils import connection

import asyncio
import websockets.server
import json


async def race(fcn1: Callable, args1: list, fcn2: Callable, args2: list, timeout=None):
    done, pending = await asyncio.wait(
        [fcn1(*args1), fcn2(*args2)], return_when=asyncio.FIRST_COMPLETED, timeout=timeout)

    for task in pending:
        task.cancel()

    # for task in done:
    #     print(task)


async def receive_request(websocket: WebSocketServerProtocol, queue: asyncio.Queue):
    try:
        async for message in websocket:
            data = json.loads(message)
            print_v(f"Received {str(data)} from websocket")
            await queue.put(data)
            return str(data)
    except ConnectionClosed or AttributeError as e:
        print_v(e)
        await asyncio.sleep(0)


async def send_data(websocket: WebSocketServerProtocol, queue: asyncio.Queue):
    out = await queue.get()
    if connection['live'] or 'id' in out.keys() or 'echo' in out.keys():
        print_v(f"Sending {str(out)} to websocket")
        try:
            await websocket.send(json.dumps(out))
        except ConnectionClosed as e:
            print_v(e)
            # Replace the outgoing message in the queue if it could not be sent
            # await queue.put(out)
    await asyncio.sleep(0)


async def send_request(websocket: WebSocketClientProtocol, message: dict | asyncio.Queue, outcome_queue: asyncio.Queue):
    if type(message) is dict:
        out = message
    elif type(message) is asyncio.Queue:
        out = await message.get()
    else:
        raise TypeError(
            f"send() got message of type {type(message)} as input. Input should be a dict or asyncio.Queue of dicts.")

    if type(out) is dict:
        if 'dummy' in out.keys():
            return

    print(f"Sending {str(out)} to websocket")
    try:
        async with websocket as socket:
            # send_str = json.dumps(out)
            # async def thread_send():
            await socket.send(json.dumps(out))
            # asyncio.run_coroutine_threadsafe(thread_send(), asyncio.get_running_loop())
    except OSError or ConnectionRefusedError as e:
        await outcome_queue.put({'Exception': e})
    await asyncio.sleep(0)


async def receive_data(websocket: WebSocketClientProtocol, in_queue: asyncio.Queue):
    try:
        async with websocket as socket:
            async for message in socket:
                # message = await socket.recv()
                # print('Incoming message received. Decoding.')
                decoded_message = json.loads(message)
                print(f"Received {decoded_message} from websocket")
                await in_queue.put(decoded_message)
    except Exception as e:
        print(e)
    await asyncio.sleep(0)


# Websockets handler
async def handler(
        websocket: (WebSocketClientProtocol | WebSocketServerProtocol),
        queue_out: asyncio.Queue,
        queue_in: asyncio.Queue,
        tx_fcn: (WebSocketServerProtocol | WebSocketClientProtocol, asyncio.Queue),
        rx_fcn: (WebSocketServerProtocol | WebSocketClientProtocol, asyncio.Queue),
        outcome_queue=None,
):
    # rx = functools.partial(rx_fcn, websocket, queue_in)

    async def rx(socket):
        await rx_fcn(socket, queue_in)

    if type(outcome_queue) is asyncio.Queue:
        async def tx(socket):
            await tx_fcn(socket, queue_out, outcome_queue)
    else:
        async def tx(socket):
            await tx_fcn(socket, queue_out)

    await race(rx, [websocket], tx, [websocket])
    # await asyncio.sleep(0.1)
    # return True


async def client_handler(
        websocket: (WebSocketClientProtocol | WebSocketServerProtocol),
        queue_out: asyncio.Queue,
        queue_in: asyncio.Queue,
        tx_fcn: (WebSocketServerProtocol | WebSocketClientProtocol, asyncio.Queue),
        rx_fcn: (WebSocketServerProtocol | WebSocketClientProtocol, asyncio.Queue),
        outcome_queue=None,
):
    async def rx(socket):
        await rx_fcn(socket, queue_in)

    if type(outcome_queue) is asyncio.Queue:
        async def tx(socket):
            await tx_fcn(socket, queue_out, outcome_queue)
    else:
        async def tx(socket):
            await tx_fcn(socket, queue_out)

    await asyncio.wait_for(tx(websocket), timeout=0.1)
    await asyncio.wait_for(rx(websocket), timeout=0.1)


async def start_server(
        tx_fcn: (WebSocketServerProtocol, asyncio.Queue),
        rx_fcn: (WebSocketServerProtocol, asyncio.Queue),
        host="localhost",
        port=1230):
    print_v(f"Starting server at {host}:{port}")

    async def server_handler(websocket):
        await handler(websocket, send_queue, receive_queue, tx_fcn, rx_fcn)

    await websockets.server.serve(server_handler, host, port, open_timeout=None, ping_timeout=None, ping_interval=None)
    await asyncio.sleep(0)

    # stop = asyncio.Future()
    # while True:
    '''
    loop = asyncio.get_event_loop()
    serve = functools.partial(websockets.server.serve, queued_handler, host, port, compression=None, open_timeout=None, ping_timeout=None, ping_interval=None)
    print_v('Awaiting server routine')
    await serve()
    print_v('Server routine done')
    '''

    '''
    stop = asyncio.Future()
    async with websockets.server.serve(queued_handler, host, port, compression=None, open_timeout=None, ping_timeout=None, ping_interval=None):
        await stop
    '''


# Define the update function here to use local queue context
async def send_update(status='event', name=''):
    # Create message template for coroutine reporting

    if name:
        out_name = name
    else:
        out_name = get_fcn_name()

    coro_status = {
        'id': out_name,
        'status': status,
        'timestamp': next(log_timestamp())
    }

    await send_queue.put(coro_status)
