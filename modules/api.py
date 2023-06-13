import functools

from websockets.exceptions import ConnectionClosed
from websockets.legacy.client import WebSocketClientProtocol
from websockets.legacy.server import WebSocketServerProtocol

from modules.config import send_queue, receive_queue
from modules.logutils import print_v, get_fcn_name, log_timestamp
from modules.sigutils import connection

import asyncio
import websockets.server
import json


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
        for key in out.keys():
            if key == 'dummy':
                return

        print(f"Sending {str(out)} to websocket")
    try:
        async with websocket as socket:
            await socket.send(json.dumps(out))
    except OSError as e:
        await outcome_queue.put({'Exception': e})


async def receive_data(websocket: WebSocketClientProtocol, in_queue: asyncio.Queue):
    out = {}
    async with websocket as socket:
        try:
            message = await socket.recv()
            print('Incoming message received. Decoding.')
            decoded_message = json.loads(message)
            print(f"Received {decoded_message} from {socket}")
            out.update(decoded_message)
        except Exception as e:
            print(e)
            await asyncio.sleep(1)
    if out:
        await in_queue.put(out)


# Websockets handler
async def handler(
        websocket: (WebSocketClientProtocol | WebSocketServerProtocol | None),
        uri: str | None,
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

    if websocket:
        done, pending = await asyncio.wait([rx(websocket), tx(websocket)], return_when=asyncio.FIRST_COMPLETED)
    elif uri:
        with websockets.WebSocketClientProtocol.connect(uri=uri) as socket:
            done, pending = await asyncio.wait([rx(socket), tx(socket)], return_when=asyncio.FIRST_COMPLETED)

    for task in done:
        print(f"Finished task {str(task)}")

    for task in pending:
        task.cancel()
        print(f"Cancelling pending task {str(task)}")
    await asyncio.sleep(0)


async def start_server(
        tx_fcn: (WebSocketServerProtocol, asyncio.Queue),
        rx_fcn: (WebSocketServerProtocol, asyncio.Queue),
        host="localhost",
        port=1230):
    print_v(f"Starting server at {host}:{port}")

    async def server_handler(websocket):
        await handler(websocket, None, send_queue, receive_queue, tx_fcn, rx_fcn)

    await websockets.server.serve(server_handler, host, port, open_timeout=None, close_timeout=None, ping_interval=None, ping_timeout=None)
    await asyncio.sleep(2)

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
