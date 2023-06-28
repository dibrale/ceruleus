# Unpause script for Ceruleus for headless operation
# A little overbuilt, as it was adapted quickly from the api-test script
import argparse

import websockets.client
import asyncio
import json

parser = argparse.ArgumentParser(
                    prog='unpause',
                    description='Unpause Ceruleus from command line',
                    epilog='Visit https://github.com/dibrale/ceruleus for more information')

parser.add_argument('--host', default='localhost', help='Name of host where Ceruleus is running', required=False)
parser.add_argument('--port', default='1230', help='Port Ceruleus is running on', required=False)


async def unpause(arg):
    uri = f"ws://{arg.host}:{arg.port}"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.client.connect(uri) as websocket:
            out = {'pause': 'false'}
            try:
                print(f"Sending: {str(out)}")
                await asyncio.wait_for(websocket.send(json.dumps(out)), 1)

            except Exception as e:
                print(e)
    except Exception as e:
        print(e)

if __name__ == "__main__":
    args = parser.parse_args()
    asyncio.run(unpause(args))



