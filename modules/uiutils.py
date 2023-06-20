import json
import re
from json import JSONDecodeError
from typing import Any

import PySimpleGUI as Sg
import functools
import asyncio
from asyncio import AbstractEventLoop

import aiofiles
import os

folder_icon = b'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABnUlEQVQ4y8WSv2rUQRSFv7vZgJFFsQg2EkWb4AvEJ8hqKVilSmFn3iNvIAp21oIW9haihBRKiqwElMVsIJjNrprsOr/5dyzml3UhEQIWHhjmcpn7zblw4B9lJ8Xag9mlmQb3AJzX3tOX8Tngzg349q7t5xcfzpKGhOFHnjx+9qLTzW8wsmFTL2Gzk7Y2O/k9kCbtwUZbV+Zvo8Md3PALrjoiqsKSR9ljpAJpwOsNtlfXfRvoNU8Arr/NsVo0ry5z4dZN5hoGqEzYDChBOoKwS/vSq0XW3y5NAI/uN1cvLqzQur4MCpBGEEd1PQDfQ74HYR+LfeQOAOYAmgAmbly+dgfid5CHPIKqC74L8RDyGPIYy7+QQjFWa7ICsQ8SpB/IfcJSDVMAJUwJkYDMNOEPIBxA/gnuMyYPijXAI3lMse7FGnIKsIuqrxgRSeXOoYZUCI8pIKW/OHA7kD2YYcpAKgM5ABXk4qSsdJaDOMCsgTIYAlL5TQFTyUIZDmev0N/bnwqnylEBQS45UKnHx/lUlFvA3fo+jwR8ALb47/oNma38cuqiJ9AAAAAASUVORK5CYII='
file_icon = b'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsSAAALEgHS3X78AAABU0lEQVQ4y52TzStEURiHn/ecc6XG54JSdlMkNhYWsiILS0lsJaUsLW2Mv8CfIDtr2VtbY4GUEvmIZnKbZsY977Uwt2HcyW1+dTZvt6fn9557BGB+aaNQKBR2ifkbgWR+cX13ubO1svz++niVTA1ArDHDg91UahHFsMxbKWycYsjze4muTsP64vT43v7hSf/A0FgdjQPQWAmco68nB+T+SFSqNUQgcIbN1bn8Z3RwvL22MAvcu8TACFgrpMVZ4aUYcn77BMDkxGgemAGOHIBXxRjBWZMKoCPA2h6qEUSRR2MF6GxUUMUaIUgBCNTnAcm3H2G5YQfgvccYIXAtDH7FoKq/AaqKlbrBj2trFVXfBPAea4SOIIsBeN9kkCwxsNkAqRWy7+B7Z00G3xVc2wZeMSI4S7sVYkSk5Z/4PyBWROqvox3A28PN2cjUwinQC9QyckKALxj4kv2auK0xAAAAAElFTkSuQmCC'


async def refresh(ui: Sg.Window):
    await asyncio.sleep(0)
    ui.refresh()
    await asyncio.sleep(0)


def exists(var: Any) -> bool:
    try:
        var
    except NameError:
        return False
    else:
        return True


async def flash(key, ui: Sg.Window, color_low='Black', color_high='Green', interval_low=0.5, interval_high=0.5):
    high_bg = functools.partial(ui[key].Update, background_color=color_high)
    low_bg = functools.partial(ui[key].Update, background_color=color_low)
    high_bg()
    ui.refresh()
    await asyncio.sleep(interval_low)
    low_bg()
    await asyncio.sleep(interval_high)


def input_field(label='', default='', key='', length=20) -> list[Sg.Element]:
    if key == '':
        key = label.upper()
    return [Sg.Text(label), Sg.Input(size=(length, 1), default_text=default, key=key, enable_events=True)]


def space() -> list[Sg.Element]:
    return [Sg.Text('\t')]


def indicator(key='', color='green') -> list[Sg.Element]:
    return [Sg.Text('   ', background_color=color, key=key, border_width=2, relief=Sg.RELIEF_GROOVE)]


def toggle(text='', key='', tooltip='') -> list[Sg.Element]:
    if key == '':
        key = text.upper()
    slider = Sg.Slider((0, 1), 1, 1,
                       orientation='horizontal',
                       disable_number_display=True,
                       enable_events=True,
                       key=f'{key}_TOGGLE',
                       size=(7, 16),
                       tooltip=tooltip
                       )
    return [Sg.Text(text), Sg.Push(), slider] + indicator(f'{key}_LIGHT') + indicator(f'{key}_WAITING_LIGHT',
                                                                                      color='Black')


def param_table(parameters: dict, title='', key='', spaces_a=4, spaces_b=6) -> Sg.Frame:
    if key == '':
        key = title.upper()
    table_title = Sg.Text(title)
    pad_a = int(spaces_a / 2) * ' '
    pad_b = int(spaces_b / 2) * ' '
    table = Sg.Table([[k, v] for k, v in parameters.items()],
                     headings=[f'{pad_a}Parameter{pad_a}', f'{pad_b}Value{pad_b}'], key=key, justification='left',
                     select_mode=Sg.TABLE_SELECT_MODE_BROWSE, enable_events=True, num_rows=25)
    return Sg.Frame(title, [[table]])


def update_semaphore(semaphore: dict, ui: Sg.Window, color_low='Black', color_go='Green', color_stop='Red'):
    for key in semaphore.keys():
        name = str(key).upper() + "_LIGHT"
        if exists(ui[name]):
            if semaphore[key] is None:
                ui[name].Update(background_color=color_low)
            elif semaphore[key] is True:
                ui[name].Update(background_color=color_go)
            else:
                ui[name].Update(background_color=color_stop)


# Returns num_lines log file lines in a list from least to most recent
async def read_log_file(file_path: str, num_lines=int(9001)) -> list[str]:
    log_lines = []
    try:
        async with aiofiles.open(file_path, mode='r') as file:
            async for line in file:
                log_lines += [str(line).strip()]
                await asyncio.sleep(0)
    except Exception as e:
        error_type = str(type(e))
        error_str = error_type.lstrip("<class '").rstrip("'>")
        print(f"{error_str}: {e}")
    out = log_lines[-num_lines:]
    if not out:
        out = ['']
    return out


async def load_json_data(file_path: str) -> dict:
    # async with lock:
    async with aiofiles.open(file_path, mode='r') as file:
        content = await file.read()
        try:
            return json.loads(content)
        except JSONDecodeError as e:
            print(f"{e} while trying to load {file_path}. Check the integrity of this file before proceeding.")


async def write_json_data(json_data: dict | list[dict], file_path: str, ensure_ascii=False, indent=4):
    if isinstance(json_data, dict):
        out = json.dumps(json_data, ensure_ascii=ensure_ascii, indent=indent)
    elif isinstance(json_data, list):
        out = ''
        for item in json_data:
            out += json.dumps(item, ensure_ascii=ensure_ascii, indent=indent) + ','
    else:
        raise TypeError(f'Input is {type(json_data)}, but must be dict or list[dict]')
    async with aiofiles.open(file_path, mode='w') as file:
        await file.write(f"[\n{out.rstrip(',')}\n]")


def checkmark(key: str):
    return Sg.Text('V', key=key, text_color='light green', visible=False, font='Courier 14 bold')


def empty_queue(q: asyncio.Queue):
    while not q.empty():
        q.get_nowait()
        q.task_done()


def add_files_in_folder(dir_name, tree: Sg.TreeData):
    parent = dir_name
    files = os.listdir(dir_name)
    tree.Insert('', dir_name, dir_name, values=[], icon=folder_icon)
    for f in files:
        fullname = os.path.join(dir_name, f)
        if os.path.isdir(fullname):            # if it's a folder, add folder and recurse
            tree.Insert(parent, fullname, f, values=[], icon=folder_icon)
            add_files_in_folder(fullname, tree)
        else:
            tree.Insert(parent, fullname, f, values=[os.stat(fullname).st_size], icon=file_icon)


def make_blank(path: str) -> str:
    split_path = re.split(r'[.\\]', path)
    template = ''

    if split_path[0] == 'results' or split_path[0] == 'work':
        word = split_path[-2].split('_')[0]
        template = '{\n' + '    "{word}": []'.format(word=word) + '\n}'
    return template

