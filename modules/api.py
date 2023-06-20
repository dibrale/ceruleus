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


async def handler(fcn1: Callable, args1: list, fcn2: Callable, args2: list, timeout=None):
    done, pending = await asyncio.wait(
        [fcn1(*args1), fcn2(*args2)], return_when=asyncio.FIRST_COMPLETED, timeout=timeout)

    # await asyncio.sleep(0.05)

    for task in pending:
        task.cancel()


    # for task in done:
    #     print(task)


async def receive_request(websocket: WebSocketServerProtocol, in_queue: asyncio.Queue):
    try:
        async for message in websocket:
            # message = await websocket.recv()
            data = json.loads(message)
            print_v(f"Received {str(data)} from websocket")
            in_queue.put_nowait(data)
            # return str(data)
    except ConnectionClosed or AttributeError as e:
        print_v(e)
    await asyncio.sleep(0)


async def send_data(websocket: WebSocketServerProtocol, out_queue: asyncio.Queue):
    out = await out_queue.get()
    while True:
        if (connection['live'] or 'id' in out.keys() or 'echo' in out.keys()) and out:
            print_v(f"Sending {str(out)} to websocket")
            try:
                await websocket.send(json.dumps(out))
            except Exception as e:
                print_v(e)
        if out_queue.empty():
            break
        else:
            out = await out_queue.get()
    await asyncio.sleep(0)


async def send_request(websocket: WebSocketClientProtocol, out_queue: asyncio.Queue, outcome_queue: asyncio.Queue):

    out = await out_queue.get()

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
        outcome_queue.put_nowait({'Exception': e})
    await asyncio.sleep(0)


async def receive_data(websocket: WebSocketClientProtocol, in_queue: asyncio.Queue, outcome_queue: asyncio.Queue):
    output = {}
    try:
        async with websocket as socket:
            async for message in socket:
                # message = await socket.recv()
                # print('Incoming message received. Decoding.')
                decoded_message = json.loads(message)
                print(f"Received {decoded_message} from websocket")
                output.update(decoded_message)
        if output:
            in_queue.put_nowait(output)
    except Exception as e:
        print(e)
        outcome_queue.put_nowait({'Exception': e})
    await asyncio.sleep(0)


async def client_handler(
        websocket: WebSocketClientProtocol,
        queue_out: asyncio.Queue,
        queue_in: asyncio.Queue,
        tx_fcn: (WebSocketClientProtocol, asyncio.Queue, asyncio.Queue),
        rx_fcn: (WebSocketClientProtocol, asyncio.Queue, asyncio.Queue),
        outcome_queue: asyncio.Queue,
):
    # rx = functools.partial(rx_fcn, in_queue=queue_in, outcome_queue=outcome_queue)
    # tx = functools.partial(tx_fcn, out_queue=queue_out, outcome_queue=outcome_queue)

    await handler(rx_fcn, [websocket, queue_in, outcome_queue], tx_fcn, [websocket, queue_out, outcome_queue])


async def start_server(
        tx_fcn: (WebSocketServerProtocol, asyncio.Queue),
        rx_fcn: (WebSocketServerProtocol, asyncio.Queue),
        host="localhost",
        port=1230):
    print_v(f"Starting server at {host}:{port}")

    async def server_handler(websocket):
        # await handler(websocket, send_queue, receive_queue, tx_fcn, rx_fcn)
        await handler(rx_fcn, [websocket, receive_queue], tx_fcn, [websocket, send_queue])
        await asyncio.sleep(0)

    server = await websockets.server.serve(server_handler, host, port)
    await server.serve_forever()

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
