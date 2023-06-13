import json
from json import JSONDecodeError

from modules.logutils import print_v
from modules.stringutils import assure_string
from modules.config import params
import aiofiles


# Asynchronously reads the content of a text file
async def read_text_file(filename: str) -> str:
    # async with lock:
    async with aiofiles.open(filename, mode='r') as file:
        print_v(f'Loading {filename}', params['verbose'])
        content = await file.read()
        print_v(f'Loaded {filename} as text file', params['verbose'])
        print_v(f'Loaded {filename}', not params['verbose'])
        return assure_string(content)


# Asynchronously writes the content of a text file
async def write_text_file(content: str, filename: str):
    # async with lock:
    async with aiofiles.open(filename, mode='w') as file:
        print_v(f'Writing {filename}', params['verbose'])
        await file.write(content)
        print_v(f'Wrote {filename} as text file', params['verbose'])
        print_v(f'Wrote {filename}', not params['verbose'])


# Load JSON data from file
async def load_json_data(file_path: str) -> dict:
    # async with lock:
    async with aiofiles.open(file_path, mode='r') as file:
        print_v(f'Loading {file_path}', params['verbose'])
        content = await file.read()
        print_v(f"Loaded {file_path} as JSON", params['verbose'])
        print_v(f"Loaded {file_path}", not params['verbose'])
        try:
            return json.loads(assure_string(content))
        except JSONDecodeError as e:
            print_v(f"{e} while trying to load {file_path}. Check the integrity of this file before proceeding.")
            quit()


# Write JSON data from file
async def write_json_data(json_data: dict, file_path: str, ensure_ascii=False, indent=4):
    # async with lock:
    async with aiofiles.open(file_path, mode='w') as file:
        print_v(f'Writing {file_path}', params['verbose'])
        await file.write(json.dumps(json_data, ensure_ascii=ensure_ascii, indent=indent))
        print_v(f"Wrote {file_path} as JSON", params['verbose'])
        print_v(f"Wrote {file_path}", not params['verbose'])


# Append to JSON file
async def append_json_data(value: any, key: str, file_path: str, ensure_ascii=False, indent=4):
    json_contents = await load_json_data(file_path)
    json_contents[key].append(value)
    await write_json_data(json_contents, file_path, ensure_ascii, indent)
