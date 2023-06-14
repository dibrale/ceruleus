import json
from json import JSONDecodeError
from typing import Any

import PySimpleGUI as Sg
import functools
import asyncio
from asyncio import AbstractEventLoop

import aiofiles

strobe_light = {
    'CONNECTION_LIGHT': False
}


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


async def strobe_visual(key, ui: Sg.Window, loop: AbstractEventLoop,
                        color_low='Black', color_high='Green',
                        interval_low=0.5, interval_high=0.5):
    while strobe_light[key]:
        flash_routine = flash(key, ui, color_low, color_high, interval_low, interval_high)
        asyncio.run_coroutine_threadsafe(flash_routine, loop)
        await flash_routine


async def strobe(key, ui: Sg.Window, loop: AbstractEventLoop):
    strobe_light.update({key: not strobe_light[key]})
    await strobe_visual(key, ui, loop)


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
