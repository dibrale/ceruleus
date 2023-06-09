import datetime
import tkinter
import typing
from asyncio.subprocess import PIPE, STDOUT
from pathlib import Path
from tkinter import filedialog

import PySimpleGUI
import websockets.client
from websockets.legacy.client import WebSocketClientProtocol

from modules.api import send_request, receive_data, client_handler
from modules.stringutils import check_nil
from modules.uiutils import *
from modules.plotutils import make_figure, pd, update_data, unassigned_template

semaphore: dict[str, bool | None] = {
    'pause': None,
    'webui': None,
    'squire': None
}

tree = {'tree': ''}
server_params = {}
llm_params = {}
webui_params = {}
process = {'data': [next(unassigned_template())]}
log = {'lines': ['']}

params: dict[str, typing.Any] = {
    'stop_ping': True,
    'stop_exchange': True,
    'uri': "ws://localhost:0",
    'socket': websockets.client.connect("ws://localhost:0"),
    'last_table_event': '',
    'second_last_table_event': '',
    'third_last_table_event': '',
    'update_table': False,
    'update_table_init': False,
    'ticks_per_update': int(10),
    'update_tick': int(0),
    'ticks_per_semaphore': int(10),
    'semaphore_tick': int(0),
    'filter_text': '',
    'ignore_list': [],
    'values': {},
    'make_connect': False,
    'do_log_update': False,
    'do_record': False,
    'closing': False,
    'live_update': False,
    'right_click_element': None
}

right_click_menu = ['', ['Copy', 'Paste', 'Select All', 'Cut']]


def make_right_click(event, menu=None):
    if menu is None:
        menu = right_click_menu
    params['right_click_element'] = event
    return menu


async def semaphore_manager(signals: dict, ui: Sg.Window):
    while 1:
        update_semaphore(signals, ui)
        for item in signals.keys():
            name = item.upper() + "_TOGGLE"
            if signals[item] is None:
                ui[name].Update(value=0, disabled=True)
            elif signals[item]:
                ui[name].Update(value=0, disabled=False)
            else:
                ui[name].Update(value=1, disabled=False)
        await asyncio.sleep(0)
        # await refresh(ui)


def switch_semaphore(ui: Sg.Window, key: str, values: dict, send_queue: asyncio.Queue):
    new_state = not bool(values[key])
    ui[key].Update(disabled=True)
    semaphore.update({key[:-7].lower(): new_state})
    send_queue.put_nowait({key[:-7].lower(): new_state})


async def message_processor(receive_queue: asyncio.Queue, handshake_queue: asyncio.Queue, report_queue: asyncio.Queue):
    while 1:
        id_out = {}
        message = await receive_queue.get()
        # print(f"Got {str(message)} from receive queue")
        for key in message.keys():
            # print(f"Processing {key}")
            item = {key: message[key]}
            if key == 'script_name':
                handshake_queue.put_nowait(item)
            elif key in semaphore.keys():
                window['STATUS'].Update('Got semaphore status')
                semaphore.update(item)
            elif key == 'id':
                id_out.update(item)
            elif not (params['closing'] or params['make_connect']):
                if key == 'waiting':
                    window['STATUS'].Update(f"Waiting at {message[key]}")
                    try:
                        asyncio.run_coroutine_threadsafe(flash(
                            f"{item[key].upper()}_WAITING_LIGHT", window, color_high='yellow'), asyncio.get_running_loop())
                    except Exception as e:
                        print(e)
                elif key == 'going':
                    window['STATUS'].Update(f"Resuming at {message[key]}")
                    try:
                        asyncio.run_coroutine_threadsafe(flash(
                            f"{item[key].upper()}_WAITING_LIGHT", window, color_high='green'), asyncio.get_running_loop())
                    except Exception as e:
                        print(e)

        if id_out and params['do_record']:
            data_framelet = {'task': message['id']}

            if message['status'].endswith('start'):
                window['STATUS'].Update(f"Starting subtask '{message['id']}'")
                data_framelet.update({'start': message['timestamp']})
                prefix = message['status'][:message['status'].find('start')]
                if prefix:
                    data_framelet['task'] = prefix + data_framelet['task']

            if message['status'] == 'stop':
                data_framelet.update({'stop': message['timestamp']})

            if message['status'] == 'event':
                data_framelet.update({'start': message['timestamp']})
                data_framelet.update({'stop': message['timestamp'] + 1})

            report_queue.put_nowait(data_framelet)
        # await asyncio.sleep(0)


async def close_connection(close_message_queue: asyncio.Queue, send_queue: asyncio.Queue, receive_queue: asyncio.Queue):
    while 1:
        await asyncio.sleep(0)
        text = await close_message_queue.get()
        params['closing'] = True
        window['STATUS'].Update('Closing connection')
        send_queue.put_nowait({'close': None})

        while not send_queue.empty():
            await asyncio.sleep(0)
        params['stop_exchange'] = True
        while not receive_queue.empty():
            receive_queue.get_nowait()
        window['RECORD'].Update('Record', button_color='green', disabled=True)
        params['do_record'] = False

        # Turn off the semaphore
        semaphore.update({key: None for key in semaphore})

        window['CONNECTION_LIGHT'].Update(background_color='Black')
        window['STATUS'].Update(text)
        window['CONNECT'].Update(disabled=False)
        window['DISCONNECT'].Update(disabled=True)
        params['closing'] = False
        # await asyncio.sleep(0)


def table_reload(tracker: dict, table_key: str):
    window[table_key].Update([[k, v] for k, v in tracker.items()])


def log_reload(values):
    lines_out = []
    # print(f"Ignore list: {params['ignore_list']}. Nil: {check_nil(params['ignore_list'])}")
    # print(f"Include item: {params['filter_text']}. Nil: {check_nil(params['filter_text'])}")
    for line in log['lines']:
        ignore_line = False
        if not check_nil(params['ignore_list']):
            for phrase in params['ignore_list']:
                if phrase in line:
                    ignore_line = True
                    break
            if ignore_line:
                continue
        if not check_nil(params['filter_text']):
            if params['filter_text'] in line:
                if values['DEL_FILTER']:
                    filter_start = line.find(params['filter_text'])
                    line = ''.join([line[:filter_start], line[filter_start + len(params['filter_text']):]])
            else:
                continue
        lines_out.append(line)

    params['do_log_update'] = True
    log.update({'lines': lines_out})


async def log_updater():
    while 1:
        await asyncio.sleep(0)
        if params['live_update']:
            log['lines'] = await read_log_file(params['values']['LOG_PATH'])
            # print('Read log file')
            log_reload(params['values'])
            # print('Reloaded log lines')


async def client_handler_wrapper(
        send_queue: asyncio.Queue,
        receive_queue: asyncio.Queue,
        outcome_queue: asyncio.Queue,
        tx_fcn: (WebSocketClientProtocol, asyncio.Queue),
        rx_fcn: (WebSocketClientProtocol, asyncio.Queue),
):

    while 1:
        await asyncio.sleep(0)
        if not params['stop_exchange']:
            handler_routine = await asyncio.to_thread(client_handler, params['socket'], send_queue, receive_queue,
                                                      tx_fcn, rx_fcn, outcome_queue)
            await handler_routine


async def make_connect(out_queue: asyncio.Queue, hi_queue: asyncio.Queue, attempts=3):
    attempt = 0
    while 1:
        await asyncio.sleep(0)

        if params['make_connect']:
            attempt += 1
            params.update({'host': str(params['values']['HOST']), 'port': str(params['values']['PORT'])})
            params.update({'uri': f"ws://{params['host']}:{params['port']}"})
            params.update({'socket': websockets.client.connect(params['uri'])})

            window['STATUS'].Update(f"Connecting to {params['uri']}...")
            window['CONNECT'].Update(disabled=True)
            window['CONNECTION_LIGHT'].Update(background_color='Yellow')
            window['RECORD'].Update('Record', button_color='green', disabled=True)
            params['do_record'] = False

            out_queue.put_nowait({'query': 'id'})
            params.update({'stop_exchange': False})
            window['STATUS'].Update(f"Sending request to {params['host']}:{params['port']}...")

            try:
                reply = await asyncio.wait_for(hi_queue.get(), 3)
            except asyncio.exceptions.TimeoutError:
                window['CONNECTION_LIGHT'].Update(background_color='Black')
                params.update({'stop_exchange': True})
                window['CONNECT'].Update(disabled=False)
                if attempt == attempts:
                    attempt = 0
                    window['STATUS'].Update('Connection attempt failed')
                    params['make_connect'] = False
                continue

            if 'script_name' in reply.keys():
                window['STATUS'].Update(f"Connected to {reply['script_name']}")
                window['DISCONNECT'].Update(disabled=False)

                window['CONNECTION_LIGHT'].Update(background_color='Green')
                window['RECORD'].Update(disabled=False)
                attempt = 0

            params['make_connect'] = False
            params['semaphore_tick'] = 0


def do_clipboard_operation(event, element):

    if event == 'Select All':
        element.Widget.selection_clear()
        element.Widget.tag_add('sel', '1.0', 'end')
    elif event == 'Copy':
        try:
            text = element.Widget.selection_get()
            window.TKroot.clipboard_clear()
            window.TKroot.clipboard_append(text)
        except Exception as e:
            print(e)
            print('Nothing selected')
    elif event == 'Paste':
        element.Widget.insert(Sg.tk.INSERT, window.TKroot.clipboard_get())
    elif event == 'Cut':
        try:
            text = element.Widget.selection_get()
            window.TKroot.clipboard_clear()
            window.TKroot.clipboard_append(text)
            element.update('')
        except Exception as e:
            print(e)
            print('Nothing selected')


async def window_update(request_queue: asyncio.Queue, data_queue: asyncio.Queue,
                        handshake_queue: asyncio.Queue,
                        outcome_queue: asyncio.Queue, framelet_queue: asyncio.Queue, loop: AbstractEventLoop):
    while 1:
        # event, values = window.read(timeout=100)
        event, values = window.read(timeout=80)
        check_key = ''
        params['values'] = values
        await asyncio.sleep(0.01)

        if event in right_click_menu[1]:
            do_clipboard_operation(event, window.find_element_with_focus())

        if event == '__TIMEOUT__':

            if params['do_log_update']:
                window['LOG'].Update('\n'.join(log['lines']))
                params['do_log_update'] = False

            if not params['stop_exchange'] and not params['make_connect']:
                if params['semaphore_tick'] == params['ticks_per_semaphore']:
                    params['semaphore_tick'] = 0
                    # await asyncio.sleep(0)
                    for key in semaphore.keys():
                        if semaphore[key] is None:
                            window['STATUS'].Update('Requesting semaphore status')
                            request_queue.put_nowait({'query': 'semaphore'})
                            break
                else:
                    params['semaphore_tick'] += 1

                framelet_queue.put_nowait({'update': 0})
                if params['do_record'] and window['TABS'].get() == 'Status':
                    data = await loop.run_in_executor(None, make_figure, pd.DataFrame(process['data']))
                    # window['GRAPH_IMAGE'].Update(data=make_figure(pd.DataFrame(process['data'])))
                    window['GRAPH_IMAGE'].Update(data=data)
            else:
                for key in semaphore.keys():
                    semaphore[key] = None

        elif event == "CONNECT":
            empty_queue(request_queue)
            empty_queue(data_queue)
            empty_queue(handshake_queue)
            empty_queue(outcome_queue)

            params['make_connect'] = True

            # asyncio.run_coroutine_threadsafe(make_connect(values, request_queue, handshake_queue), loop)

        elif event == 'PARAMS_PATH':
            path = Path(values['PARAMS_PATH'])
            window['SAVE_CHECK'].Update(visible=False)
            window['LOAD_CHECK'].Update(visible=False)
            if path.is_file():
                window['PARAMS_LOAD'].Update(disabled=False)
                window['PARAMS_SAVE'].Update(disabled=False)
            elif path.is_dir():
                window['PARAMS_LOAD'].Update(disabled=True)
                window['PARAMS_SAVE'].Update(disabled=True)
            else:
                window['PARAMS_LOAD'].Update(disabled=True)
                if server_params or llm_params or webui_params:
                    window['PARAMS_SAVE'].Update(disabled=False)
                else:
                    window['PARAMS_SAVE'].Update(disabled=True)

        elif event == 'PARAMS_LOAD':
            [server, llm, webui] = await load_json_data(values['PARAMS_PATH'])
            server_params.update(server)
            llm_params.update(llm)
            webui_params.update(webui)
            window['SERVER_PARAMS'].update([[k, v] for k, v in server_params.items()])
            window['LLM_PARAMS'].update([[k, v] for k, v in llm_params.items()])
            window['WEBUI_PARAMS'].update([[k, v] for k, v in webui_params.items()])
            window['LOAD_CHECK'].Update(visible=True)
            params.update({'update_table_init': False})
            params.update({'update_table': False})

        elif event == 'PARAMS_SAVE':
            await write_json_data([server_params, llm_params, webui_params], values['PARAMS_PATH'])
            window['SAVE_CHECK'].Update(visible=True)

        elif event == 'PARAMS_MODIFY':
            window['SAVE_CHECK'].Update(visible=False)
            window['LOAD_CHECK'].Update(visible=False)
            new_param = {values['PARAMETER']: values['VALUE']}

            if values['SERVER']:
                server_params.update(new_param)
                window['SERVER_PARAMS'].Update([[k, v] for k, v in server_params.items()])
            elif values['LLM']:
                llm_params.update(new_param)
                window['LLM_PARAMS'].Update([[k, v] for k, v in llm_params.items()])
            elif values['WEBUI']:
                webui_params.update(new_param)
                window['WEBUI_PARAMS'].Update([[k, v] for k, v in webui_params.items()])
            else:
                continue

        if event in ['PARAMETER', 'VALUE', 'PARAMS_DELETE', 'PARAMS_MODIFY', 'PARAMS_LOAD', 'SERVER', 'LLM',
                     'WEBUI'] or str(event).endswith('_PARAMS'):
            # Remove row highlighting from previous table when switching tables
            if str(event).endswith('_PARAMS') and event != (params['last_table_event']):
                if not params['update_table_init']:
                    params['last_table_event'] = event

                if params['update_table']:
                    if params['last_table_event'] == 'SERVER_PARAMS':
                        window['SERVER_PARAMS'].Update([[k, v] for k, v in server_params.items()])
                    elif params['last_table_event'] == 'LLM_PARAMS':
                        window['LLM_PARAMS'].Update([[k, v] for k, v in llm_params.items()])
                    elif params['last_table_event'] == 'WEBUI_PARAMS':
                        window['WEBUI_PARAMS'].Update([[k, v] for k, v in webui_params.items()])

                    params.update({'last_table_event': event})

                    params['update_table'] = False
                else:
                    params['update_table'] = True
                    if params['update_table_init']:
                        continue
                    else:
                        params['update_table_init'] = True

            if event == 'SERVER_PARAMS':
                window['SERVER'].Update(True)
                window['LLM'].Update(False)
                window['WEBUI'].Update(False)
                key_list = []
                for key in server_params.keys():
                    key_list += [key]
                try:
                    window['PARAMETER'].Update(key_list[int(values['SERVER_PARAMS'][0])])
                    check_key = key_list[int(values['SERVER_PARAMS'][0])]
                    window['VALUE'].Update(server_params[key_list[int(values['SERVER_PARAMS'][0])]])
                except IndexError as e:
                    pass

            elif event == 'LLM_PARAMS':
                window['SERVER'].Update(False)
                window['LLM'].Update(True)
                window['WEBUI'].Update(False)
                key_list = []
                for key in llm_params.keys():
                    key_list += [key]
                try:
                    window['PARAMETER'].Update(key_list[int(values['LLM_PARAMS'][0])])
                    check_key = key_list[int(values['LLM_PARAMS'][0])]
                    window['VALUE'].Update(llm_params[key_list[int(values['LLM_PARAMS'][0])]])
                except IndexError as e:
                    pass

            elif event == 'WEBUI_PARAMS':
                window['SERVER'].Update(False)
                window['LLM'].Update(False)
                window['WEBUI'].Update(True)
                key_list = []
                for key in webui_params.keys():
                    key_list += [key]
                try:
                    window['PARAMETER'].Update(key_list[int(values['WEBUI_PARAMS'][0])])
                    check_key = key_list[int(values['WEBUI_PARAMS'][0])]
                    window['VALUE'].Update(webui_params[key_list[int(values['WEBUI_PARAMS'][0])]])
                except IndexError as e:
                    pass

            if str(event).endswith('_PARAMS') or ((bool(values['VALUE']) | bool(values['PARAMETER'])) & (
                    values['SERVER'] | values['LLM'] | values['WEBUI'] | (event in ['SERVER', 'LLM', 'WEBUI']))):
                window['PARAMS_MODIFY'].Update(disabled=False)
            else:
                window['PARAMS_MODIFY'].Update(disabled=True)

            if (event in ['PARAMETER', 'VALUE', 'PARAMS_DELETE', 'PARAMS_MODIFY', 'PARAMS_LOAD'] and values[
                'SERVER']) or str(event).startswith('SERVER'):
                check_dict = server_params
                check_table = 'SERVER_PARAMS'
            elif (event in ['PARAMETER', 'VALUE', 'PARAMS_DELETE', 'PARAMS_MODIFY', 'PARAMS_LOAD'] and values[
                'LLM']) or str(event).startswith('LLM'):
                check_dict = llm_params
                check_table = 'LLM_PARAMS'
            elif (event in ['PARAMETER', 'VALUE', 'PARAMS_DELETE', 'PARAMS_MODIFY', 'PARAMS_LOAD'] and values[
                'WEBUI']) or str(event).startswith('WEBUI'):
                check_dict = webui_params
                check_table = 'WEBUI_PARAMS'
            else:
                continue

            if event in ['SERVER', 'LLM', 'WEBUI']:
                check_key = values['PARAMETER']
            elif event in ['PARAMETER', 'PARAMS_MODIFY', 'PARAMS_LOAD']:
                check_key = values['PARAMETER']
            if not exists(check_key):
                check_key = ''

            window['PARAMS_DELETE'].Update(disabled=True)
            check_keys = list(check_dict.keys())
            for key in check_keys:
                if key == check_key:
                    window['PARAMS_DELETE'].Update(disabled=False)

            if event in ['SERVER', 'LLM', 'WEBUI', 'PARAMETER', 'PARAMS_MODIFY', 'PARAMS_LOAD']:
                try:
                    window[check_table].Update(select_rows=[check_keys.index(check_key)])
                except ValueError:
                    pass

        if event == 'PARAMS_DELETE':
            key = values['PARAMETER']
            window['SAVE_CHECK'].Update(visible=False)
            window['LOAD_CHECK'].Update(visible=False)
            if values['SERVER']:
                server_params.__delitem__(key)
                table_reload(server_params, 'SERVER_PARAMS')
                params.update({'last_table_event': 'SERVER_PARAMS'})
            elif values['LLM']:
                llm_params.__delitem__(key)
                table_reload(llm_params, 'LLM_PARAMS')
                params.update({'last_table_event': 'LLM_PARAMS'})
            elif values['WEBUI']:
                webui_params.__delitem__(key)
                table_reload(webui_params, 'WEBUI_PARAMS')
                params.update({'last_table_event': 'WEBUI_PARAMS'})
            params.update({'update_table_init': False})
            params.update({'update_table': False})

        elif event == "DISCONNECT":
            window['CONNECT'].Update(disabled=True)
            await outcome_queue.put("Connection closed")

        if event[-7:] == '_TOGGLE':
            switch_semaphore(window, event, values, request_queue)

        elif event == 'LOG_PATH':
            path = Path(values['LOG_PATH'])
            window['LOG_CHECK'].Update(visible=False)
            window['LIVE_UPDATE'].Update(value=False, disabled=True)
            if path.is_file():
                window['LOG_LOAD'].Update(disabled=False)
            else:
                window['LOG_LOAD'].Update(disabled=True)

        elif event == 'LOG_LOAD':
            log['lines'] = await read_log_file(values['LOG_PATH'])
            window['LOG_CHECK'].Update(visible=True)
            log_reload(values)
            params['do_log_update'] = True
            window['LIVE_UPDATE'].Update(disabled=False)

        elif event == 'LIVE_UPDATE':
            params['live_update'] = values['LIVE_UPDATE']

        elif str(event).endswith('FILTER'):
            if not values['FILTER'] and not values['IGNORE_FILTER']:
                window['APPLY_FILTER'].Update(disabled=True)
                window['CLEAR_FILTER'].Update(disabled=False)
            else:
                window['APPLY_FILTER'].Update(disabled=False)
                window['CLEAR_FILTER'].Update(disabled=False)

            if event == 'APPLY_FILTER':
                params['filter_text'] = values['FILTER']
                params['ignore_list'] = values['IGNORE_FILTER'].split(',')
                window['APPLY_FILTER'].Update(disabled=True)

            elif event == 'CLEAR_FILTER':
                params['filter_text'] = ''
                params['ignore_list'] = []
                window['FILTER'].Update('')
                window['IGNORE_FILTER'].Update('')
                window['APPLY_FILTER'].Update(disabled=True)
                window['CLEAR_FILTER'].Update(disabled=True)

            elif event == 'DEL_FILTER':
                pass

            log_reload(values)

        elif event == 'TOUCH':
            if os.name == 'nt':
                command_text = f"powershell (Get-Item \"{values['SQUIRE_OUT_PATH']}\").LastWriteTime=$(Get-Date -format o)"
            else:
                command_text = f"touch {values['SQUIRE_OUT_PATH']}"

            # os.system(command_text)
            touch = await asyncio.create_subprocess_shell(command_text, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
            await touch.wait()

        elif event == 'OPEN_RESULT':
            async with aiofiles.open(values['TREE'][0], mode='r') as file:
                content = await file.read()
                window['FILE_TEXT'].update(content)

        elif event == 'MAKE_RESULT':
            window['FILE_TEXT'].update(make_blank(values['TREE'][0]))

        elif event == 'SAVE_RESULT':
            async with aiofiles.open(values['TREE'][0], mode='w') as file:
                await file.write(values['FILE_TEXT'])
            tree['tree'] = make_tree()
            window['TREE'].Update(tree['tree'])

        elif event == 'TREE':
            if Path.is_file(Path(values['TREE'][0])) and (
                    values['TREE'][0].endswith('.json') or values['TREE'][0].endswith('.txt')):
                window['OPEN_RESULT'].Update(disabled=False)
                window['SAVE_RESULT'].Update(disabled=False)
                if values['TREE'][0].endswith('.json'):
                    window['MAKE_RESULT'].Update(disabled=False)
                else:
                    window['MAKE_RESULT'].Update(disabled=True)
            else:
                window['OPEN_RESULT'].Update(disabled=True)
                window['SAVE_RESULT'].Update(disabled=True)
                window['MAKE_RESULT'].Update(disabled=True)

        elif event == 'RECORD':
            if params['do_record']:
                window['RECORD'].Update('Record', button_color='green')
                params['do_record'] = False
            else:
                window['RECORD'].Update('Pause', button_color='red')
                params['do_record'] = True

        elif event == 'CLEAR':
            framelet_queue.put_nowait({'update': 1})
            window['GRAPH_IMAGE'].Update(data=make_figure(pd.DataFrame(process['data'])))

        elif event == 'SAVE_DATA':
            save_filename = Sg.tk.filedialog.asksaveasfilename(
                defaultextension='txt',
                filetypes=(("txt", "*.txt"), ("All Files", "*.*")),
                initialdir=os.getcwd(),
                initialfile='ceruleus_' + str(datetime.datetime.now().timestamp()) + '.txt',
                title="Save As"
            )
            if save_filename:
                try:
                    async with aiofiles.open(save_filename, mode='w') as file:
                        await file.write(str(process['data']))
                except Exception as e:
                    Sg.PopupError(str(e), title='Error', non_blocking=True)

        elif event == 'SAVE_IMAGE':
            save_filename = Sg.tk.filedialog.asksaveasfilename(
                defaultextension='png',
                filetypes=(("png", "*.png"), ("All Files", "*.*")),
                initialdir=os.getcwd(),
                initialfile='ceruleus_' + str(datetime.datetime.now().timestamp()) + '.png',
                title="Save As"
            )
            if save_filename:
                try:
                    make_figure(pd.DataFrame(process['data']), mode='write', path=save_filename)
                except Exception as e:
                    Sg.PopupError(str(e), title='Error', non_blocking=True)

        # Exit
        elif event == "Exit" or event == Sg.WIN_CLOSED:
            return

        params.update({'previous_event': event})

        await asyncio.sleep(0.01)


async def async_main():
    loop = asyncio.get_event_loop()
    request_queue = asyncio.Queue()
    data_queue = asyncio.Queue()
    handshake_queue = asyncio.Queue()
    outcome_queue = asyncio.Queue()
    framelet_queue = asyncio.Queue()

    # processor_task = loop.create_task(message_processor(data_queue, pong_queue, updates_list))
    # asyncio.run_coroutine_threadsafe(message_processor(data_queue, handshake_queue, updates_list), loop)
    processor_routine = await asyncio.to_thread(message_processor, data_queue, handshake_queue, framelet_queue)

    # handler_task = loop.create_task(client_handler_wrapper(
    #                   request_queue, data_queue, outcome_queue, send_request, receive_data, loop))
    # asyncio.run_coroutine_threadsafe(client_handler_wrapper(
    #                   request_queue, data_queue, outcome_queue, send_request, receive_data, loop), loop)
    handler_routine = await asyncio.to_thread(client_handler_wrapper, request_queue, data_queue, outcome_queue,
                                              send_request, receive_data)

    # close_task = loop.create_task(close_connection(outcome_queue, request_queue, data_queue))
    # asyncio.run_coroutine_threadsafe(close_connection(outcome_queue, request_queue, data_queue), loop)
    close_routine = await asyncio.to_thread(close_connection, outcome_queue, request_queue, data_queue)

    # semaphore_task = loop.create_task(semaphore_manager(semaphore, window))
    # asyncio.run_coroutine_threadsafe(semaphore_manager(semaphore, window), loop)
    semaphore_routine = await asyncio.to_thread(semaphore_manager, semaphore, window)

    window_task = loop.create_task(
        window_update(request_queue, data_queue, handshake_queue, outcome_queue, framelet_queue, loop))
    # asyncio.run_coroutine_threadsafe(window_update(request_queue, data_queue, pong_queue, outcome_queue, loop), loop)
    # window_routine = asyncio.to_thread(window_update, request_queue, data_queue, pong_queue, outcome_queue, loop)
    # asyncio.run_coroutine_threadsafe(window_routine, loop)
    # await asyncio.gather(ping_task, close_task, semaphore_task)

    # asyncio.run_coroutine_threadsafe(make_connect(window, request_queue, handshake_queue), loop)
    connect_routine = await asyncio.to_thread(make_connect, request_queue, handshake_queue, 3)
    # connect_task = loop.create_task(make_connect(window, request_queue, handshake_queue))

    # asyncio.run_coroutine_threadsafe(log_updater(loop), loop)
    # log_task = loop.create_task(log_updater())
    log_routine = await asyncio.to_thread(log_updater)

    update_data_routine = await asyncio.to_thread(update_data, framelet_queue, process['data'])
    # update_data_routine = loop.create_task(update_data(framelet_queue, process['data']))

    # await processor_task

    # while True:
    #     await asyncio.sleep(1)

    # window.close()
    # routine_list = [close_routine, connect_routine, handler_routine, semaphore_routine,
    #                 processor_routine, log_routine, update_data_routine]
    # async with asyncio.TaskGroup() as tg:
    #     tg.create_task(window_update(request_queue, data_queue, handshake_queue, outcome_queue, framelet_queue, loop))
    #     for routine in routine_list:
    #         tg.create_task(routine)

    await asyncio.gather(window_task, close_routine, connect_routine, handler_routine, semaphore_routine,
                         processor_routine, log_routine, update_data_routine)
    # await window_task


# The GUI elements are all declared in synchronous main(), since they only need to be declared once
if __name__ == "__main__":
    # List directory contents
    tree.update({'tree': make_tree()})
    # add_files_in_folder('squire_output', tree)

    layout = [
        [Sg.TabGroup([
            [Sg.Tab('Parameters',
                    [space(),
                     [
                         Sg.Text('Path to parameter file'),
                         Sg.Input(size=(25, 1), default_text='params.json', key='PARAMS_PATH',
                                  enable_events=True, right_click_menu=right_click_menu),
                         Sg.FileBrowse(key='PARAMS_BROWSE',
                                       file_types=[("JSON Files", '*.json'), ("All Files", '.*')],
                                       initial_folder=os.getcwd(),
                                       tooltip="Browse for a params.json file"),
                         Sg.Button(button_text="Load", key='PARAMS_LOAD', disabled=True,
                                   tooltip="Load the parameter file at the selected path"),
                         checkmark('LOAD_CHECK')
                     ],
                     [
                         param_table(server_params, title='Server Parameters', key='SERVER_PARAMS',
                                     spaces_a=6, spaces_b=10),
                         param_table(llm_params, title='LLM Parameters', key='LLM_PARAMS'),
                         param_table(webui_params, title='Webui Parameters', key='WEBUI_PARAMS')
                     ],
                     [Sg.Frame('Edit Parameter', [
                         [Sg.Radio('Server', 'PARAM_RADIO', key='SERVER', enable_events=True)] +
                         [Sg.Radio('LLM', 'PARAM_RADIO', key='LLM', enable_events=True)] +
                         [Sg.Radio('Webui', 'PARAM_RADIO', key='WEBUI', enable_events=True)] + [
                             Sg.Push()],
                         input_field('Parameter', length=30, right_click_menu=right_click_menu) +
                         input_field('Value', length=60, right_click_menu=right_click_menu) +
                         [Sg.Button(button_text="Modify", key='PARAMS_MODIFY', disabled=True,
                                    tooltip="Add or modify parameter and associated value")] +
                         [Sg.Button(button_text="Delete", key='PARAMS_DELETE', disabled=True,
                                    tooltip="Delete a parameter and associated value")] +
                         [Sg.Push()],
                     ])],
                     [Sg.Button(button_text="Save", key='PARAMS_SAVE', disabled=True,
                                tooltip="Save the parameter file to the selected path"),
                      checkmark('SAVE_CHECK')],

                     ])],
            [Sg.Tab('Controls',
                    [space(),
                     [
                         Sg.Frame('Connection', [
                             input_field('Host', 'localhost', length=15, right_click_menu=right_click_menu),
                             input_field('Port', '1230', length=5, right_click_menu=right_click_menu),
                             space(),
                             [Sg.Button(button_text="Connect", key='CONNECT',
                                        tooltip="Connect to a running Ceruleus instance")] +
                             [Sg.Button(button_text="Disconnect", key='DISCONNECT', disabled=True,
                                        tooltip="Disconnect from a running Ceruleus instance")],
                         ]),
                         Sg.Frame('Semaphore', [
                             toggle('webui',
                                    tooltip="Wait just before accessing text-generation-webui API"),
                             toggle('squire', tooltip="Wait just before launching Squire"),
                             toggle('pause', tooltip="Safely pause Ceruleus"),
                             space()
                         ]),
                         Sg.Frame('Squire', [
                             [Sg.Text('Path to Squire output')],
                             [Sg.Input(size=(25, 1), default_text='squire_output/out.txt', key='SQUIRE_OUT_PATH',
                                       enable_events=True, right_click_menu=right_click_menu)],
                             [Sg.FileBrowse(key='SQUIRE_OUT_BROWSE',
                                            file_types=[("Text Files", '*.txt'), ("All Files", '.*')],
                                            initial_folder=os.getcwd(),
                                            tooltip="Browse for a Squire output file",
                                            target=(-1, 0)),
                              Sg.Button(button_text="Touch", key='TOUCH',
                                        tooltip="Touch the squire output file to begin execution")], space()
                         ])],
                     ])],
            [Sg.Tab('Status', [
                [Sg.Frame('Process History', [
                    [Sg.Image(make_figure(pd.DataFrame(process['data'])), key='GRAPH_IMAGE', expand_x=True)]
                ], expand_x=True)],
                [Sg.Button(button_text="Record", key='RECORD', disabled=True, button_color='green',
                           tooltip="Record or pause process history")] +
                [Sg.Button(button_text="Clear", key='CLEAR',
                           tooltip="Clear process history")] +
                [Sg.Button(button_text="Save Data", key='SAVE_DATA',
                           tooltip="Save process history data")] +
                [Sg.Button(button_text="Save Image", key='SAVE_IMAGE',
                           tooltip="Save process history image")] +
                [Sg.Push()]
            ])],
            [Sg.Tab('Log',
                    [space(),
                     input_field('Log file path', key='LOG_PATH', right_click_menu=right_click_menu) +
                     [Sg.FileBrowse(key='LOG_BROWSE',
                                    file_types=[("LOG Files", '*.log'), ('Text Files', '*.txt'),
                                                ("All Files", '.*')],
                                    initial_folder=os.getcwd(), tooltip="Browse for a log file")] +
                     [Sg.Button(button_text="Load", key='LOG_LOAD', disabled=True,
                                tooltip="Load the log file at the selected path"), checkmark('LOG_CHECK')],
                     [Sg.Multiline(pad=(10, 10), key='LOG', size=(130, 30), autoscroll=True, expand_x=True, expand_y=True, right_click_menu=right_click_menu, disabled=True)],
                     [Sg.Frame('Log Filters', [
                         input_field('Include item', key='FILTER') + input_field('Ignore list',
                                                                                 key='IGNORE_FILTER', length=88, right_click_menu=right_click_menu),
                         [Sg.Checkbox('Live Update', key='LIVE_UPDATE', disabled=True, enable_events=True)] +
                         [Sg.Checkbox('Remove Filtered Text', key='DEL_FILTER', enable_events=True)] +
                         [Sg.Button(button_text="Apply", key='APPLY_FILTER', disabled=True,
                                    tooltip="Apply the entered filter to the log")] +
                         [Sg.Button(button_text="Clear", key='CLEAR_FILTER', disabled=True,
                                    tooltip="Clear the filter")]
                     ], expand_x=True)]
                     ])],
            [Sg.Tab('Results',
                    [
                        [Sg.Column([
                            [Sg.Tree(data=tree['tree'],
                                     headings=['Size', ],
                                     # select_mode=Sg.TABLE_SELECT_MODE_EXTENDED,
                                     num_rows=36,
                                     col0_width=30,
                                     key='TREE',
                                     enable_events=True,
                                     expand_x=True,
                                     expand_y=True,
                                     show_expanded=True
                                     )],
                            [Sg.Button(button_text="Open", key='OPEN_RESULT', disabled=True,
                                       tooltip="Open a result or template file as text for editing")] +
                            [Sg.Button(button_text="Regenerate", key='MAKE_RESULT', disabled=True,
                                       tooltip="Create a blank result file template based on the file name")] +
                            [Sg.Button(button_text="Save", key='SAVE_RESULT', disabled=True,
                                       tooltip="Save to the selected file")]
                        ])]
                        +
                        [Sg.Multiline('', size=(82, 40), key='FILE_TEXT', expand_x=True, expand_y=True, right_click_menu=right_click_menu)]
                    ])]
        ], key='TABS')],
        [Sg.StatusBar('\t\t\t\t\t\t\t\t\t', key='STATUS'), indicator('CONNECTION_LIGHT', color='Black')[0]],
    ]

    # Declare the GUI window
    window = Sg.Window("Ceruleus Client", layout, resizable=True, finalize=True)

    asyncio.run(async_main())
