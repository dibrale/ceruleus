import asyncio
import concurrent.futures
import os
import typing
from asyncio.subprocess import PIPE, STDOUT
from pathlib import Path

import websockets.client
from websockets.legacy.client import WebSocketClientProtocol

from modules.api import send_request, receive_data, handler, client_handler
from modules.stringutils import check_nil
from modules.uiutils import *

semaphore: dict[str, bool | None] = {
    'pause': None,
    'webui': None,
    'squire': None
}

server_params = {}
llm_params = {}
webui_params = {}
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
    'ticks_per_update': int(2),
    'update_tick': int(0),
    'filter_text': '',
    'ignore_list': []
}


async def semaphore_manager(signals: dict, ui: Sg.Window):
    while True:
        update_semaphore(signals, ui)
        await asyncio.sleep(0)
        for item in signals.keys():
            name = item.upper() + "_TOGGLE"
            if signals[item] is None:
                ui[name].Update(value=0, disabled=True)
            elif signals[item]:
                ui[name].Update(value=0, disabled=False)
            else:
                ui[name].Update(value=1, disabled=False)
        await refresh(ui)


async def switch_semaphore(ui: Sg.Window, key: str, values: dict, send_queue: asyncio.Queue):
    new_state = not bool(values[key])
    ui[key].Update(disabled=True)
    semaphore.update({key[:-7].lower(): new_state})
    await refresh(ui)
    await send_queue.put({key[:-7].lower(): new_state})


async def message_processor(receive_queue: asyncio.Queue, pong_queue: asyncio.Queue, updates: list):
    while True:
        id_out = {}
        message = await receive_queue.get()
        print(f"Got {str(message)} from receive queue")
        for key in message.keys():
            print(f"Processing {key}")
            item = {key: message[key]}
            if key == 'pong':
                await pong_queue.put(item)
            elif key == 'script_name':
                await pong_queue.put(item)
            elif key in semaphore.keys():
                semaphore.update(item)
            elif key == 'id':
                id_out.update(item)
            elif key == 'waiting':
                try:
                    asyncio.run_coroutine_threadsafe(flash(
                        f"{item[key].upper()}_WAITING_LIGHT", window, color_high='yellow'), asyncio.get_running_loop())
                except Exception as e:
                    print(e)
            elif key == 'going':
                try:
                    asyncio.run_coroutine_threadsafe(flash(
                        f"{item[key].upper()}_WAITING_LIGHT", window, color_high='green'), asyncio.get_running_loop())
                except Exception as e:
                    print(e)
        if id_out:
            updates.append(id_out)
        await asyncio.sleep(0)


async def close_connection(text_queue: asyncio.Queue, send_queue: asyncio.Queue, receive_queue: asyncio.Queue):
    while True:
        await asyncio.sleep(0)
        text = await text_queue.get()
        # print(f"Got '{text}' from outcome queue")
        await send_queue.put({'close': None})
        # await asyncio.sleep(0.5)
        await send_queue.put({'dummy': None})
        params.update({'stop_ping': True})

        await asyncio.sleep(0)
        window['STATUS'].Update('Closing connection')
        window['CONNECT'].Update(disabled=True)
        window['DISCONNECT'].Update(disabled=True)
        await asyncio.sleep(0)
        # window.refresh()

        # Cancel pending rx/tx if closing

        tasks_to_close = ['handshake_reply_get', 'strobe']
        for task in asyncio.all_tasks(asyncio.get_running_loop()):
            if task.get_name() in tasks_to_close:
                task.cancel()
                await asyncio.sleep(0)

        while not send_queue.empty() or not receive_queue.empty():
            await asyncio.sleep(0)
        params.update({'stop_exchange': True})

        # Turn off the semaphore
        for key in semaphore.keys():
            semaphore[key] = None

        strobe_light['CONNECTION_LIGHT'] = False
        window['CONNECTION_LIGHT'].Update(background_color='Black')
        window['STATUS'].Update(text)
        window['CONNECT'].Update(disabled=False)


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
                    line = line[:filter_start] + line[filter_start + len(params['filter_text']):]
            else:
                continue
        lines_out.append(line)
    window['LOG'].Update('\n'.join(lines_out))


async def ping(
        send_queue: asyncio.Queue,
        pong_queue: asyncio.Queue,
        receive_queue: asyncio.Queue,
        outcome_queue: asyncio.Queue,
        timeout=10,
        period=20,
        ping_data=None,
        pong_data=None,
):
    if pong_data is None:
        pong_data = {'pong': 0}
    if ping_data is None:
        ping_data = {'ping': 0}
    put_outcome = True

    while True:
        await asyncio.sleep(0)
        off = params['stop_ping']
        if off:

            if not put_outcome:
                await outcome_queue.put('Connection closed')
                put_outcome = True

            await asyncio.sleep(0.5)
        else:
            put_outcome = True
            recirculate = {}
            try:
                await send_queue.put(ping_data)
                try:
                    done = await asyncio.wait_for(pong_queue.get(), timeout=timeout)
                except asyncio.exceptions.TimeoutError:
                    done = None
                if done:
                    got_pong = False
                    for key in done.keys():
                        if key in pong_data:
                            got_pong = True
                        else:
                            recirculate.update({key, done[key]})

                else:
                    text = f"Timed out after {str(timeout)} seconds"
                    raise TimeoutError(text)

                if got_pong:
                    await asyncio.sleep(period)

            except TimeoutError or ConnectionError as e:
                await outcome_queue.put(str(e))
                put_outcome = False

            finally:
                if recirculate:
                    await receive_queue.put(recirculate)
                await asyncio.sleep(0)


async def client_handler_wrapper(
        send_queue: asyncio.Queue,
        receive_queue: asyncio.Queue,
        outcome_queue: asyncio.Queue,
        tx_fcn: (WebSocketClientProtocol, asyncio.Queue),
        rx_fcn: (WebSocketClientProtocol, asyncio.Queue),
        loop: asyncio.AbstractEventLoop
):
    # async def queued_handler():
    #     await handler(params['socket'], send_queue, receive_queue, tx_fcn, rx_fcn, outcome_queue)

    while True:

        # handler_task = loop.create_task(queued_handler())

        if not params['stop_exchange']:
            # print(f"Awaiting handler for {str(params['socket'])}")
            await handler(params['socket'], send_queue, receive_queue, tx_fcn, rx_fcn, outcome_queue)
            # await queued_handler()
            # await handler_task
            # print('Handler done')
            await asyncio.sleep(0)
        else:
            await asyncio.sleep(1)


async def window_update(request_queue: asyncio.Queue, data_queue: asyncio.Queue, pong_queue: asyncio.Queue,
                        outcome_queue: asyncio.Queue, loop: AbstractEventLoop):
    while True:
        event, values = window.read(timeout=50)
        check_key = ''

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

        if event == "CONNECT":
            params.update({'host': str(values['HOST']), 'port': str(values['PORT'])})
            params.update({'uri': f"ws://{params['host']}:{params['port']}"})
            params.update({'socket': websockets.client.connect(params['uri'], open_timeout=None,
                                                               ping_timeout=None, ping_interval=None)})

            # asyncio.run_coroutine_threadsafe(client_handler_wrapper(
            #     request_queue, data_queue, outcome_queue, send_request, receive_data, loop), loop)
            window['STATUS'].Update(f"Connecting to {params['uri']}...")
            window['CONNECT'].Update(disabled=True)
            # window.refresh()

            window['STATUS'].Update(f"Connecting to {params['uri']}...")
            # asyncio.run_coroutine_threadsafe(strobe('CONNECTION_LIGHT', window, loop), loop)
            window['CONNECTION_LIGHT'].Update(background_color='Yellow')

            for queue in [request_queue, data_queue, pong_queue, outcome_queue, pong_queue]:
                empty_queue(queue)

            await request_queue.put({'query': 'id'})
            params.update({'stop_exchange': False})
            await asyncio.sleep(0)
            window['STATUS'].Update(f"Sending request to {params['host']}:{params['port']}...")
            # window.refresh()
            await asyncio.sleep(0)
            # awaiting_reply = True

            # pong_queue_task = loop.create_task(pong_queue.get())
            # print("Awaiting pong queue")
            await asyncio.sleep(0)
            # reply = await pong_queue_task
            # print(f"Got pong queue item: {reply}")

            reply = await pong_queue.get()
            for key in reply.keys():
                if key == 'script_name':
                    window['STATUS'].Update(f"Connected to {reply['script_name']}")
                    window['DISCONNECT'].Update(disabled=False)

                    strobe_light['CONNECTION_LIGHT'] = False

                    window['CONNECTION_LIGHT'].Update(background_color='Green')

                    await request_queue.put({'query': 'semaphore'})
                    # params.update({'stop_ping': False})

            '''
            while awaiting_reply:
                reply_task = loop.create_task(pong_queue.get(), name='handshake_reply_get')
                try:
                    reply = await reply_task
                except asyncio.exceptions.CancelledError:
                    reply = None

                try:
                    for key in reply.keys():
                        if key == 'script_name':
                            window['STATUS'].Update(f"Connected to {reply['script_name']}")
                            window['DISCONNECT'].Update(disabled=False)

                            strobe_light['CONNECTION_LIGHT'] = False
                            try:
                                await strobe_task
                            except asyncio.exceptions.CancelledError:
                                pass

                            window['CONNECTION_LIGHT'].Update(background_color='Green')

                            await request_queue.put({'query': 'semaphore'})
                            # params.update({'stop_ping': False})
                except AttributeError as e:
                    print(e)
                    params.update({'stop_exchange': True})
                    strobe_task.cancel()

                awaiting_reply = False
                '''
        if event == 'PARAMS_PATH':
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

        if event == 'PARAMS_LOAD':
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

        if event == 'LLM_PARAMS':
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

        if event == 'WEBUI_PARAMS':
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

        if event == 'PARAMS_SAVE':
            await write_json_data([server_params, llm_params, webui_params], values['PARAMS_PATH'])
            window['SAVE_CHECK'].Update(visible=True)

        if event == 'PARAMS_MODIFY':
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

        # Exit
        if event == "Exit" or event == Sg.WIN_CLOSED:
            return

        if event == "DISCONNECT":
            window['CONNECT'].Update(disabled=True)
            await outcome_queue.put("Connection closed")

        if event[-7:] == '_TOGGLE':
            await switch_semaphore(window, event, values, request_queue)

        if event == 'LOG_PATH':
            path = Path(values['LOG_PATH'])
            window['LOG_CHECK'].Update(visible=False)
            window['LIVE_UPDATE'].Update(value=False, disabled=True)
            if path.is_file():
                window['LOG_LOAD'].Update(disabled=False)
            else:
                window['LOG_LOAD'].Update(disabled=True)

        if event == 'LOG_LOAD':
            log['lines'] = await read_log_file(values['LOG_PATH'])
            window['LOG_CHECK'].Update(visible=True)
            log_reload(values)
            window['LIVE_UPDATE'].Update(value=True, disabled=False)
            window.refresh()

        if event == '__TIMEOUT__' and values['LIVE_UPDATE']:
            if params['update_tick'] > 0:
                params['update_tick'] -= 1
            else:
                params['update_tick'] = params['ticks_per_update']
                if window['LOG_CHECK'].visible is True:
                    log['lines'] = await read_log_file(values['LOG_PATH'])
                    log_reload(values)

        await asyncio.sleep(0)

        if str(event).endswith('FILTER'):
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
            log_reload(values)

        if event == 'CLEAR_FILTER':
            params['filter_text'] = ''
            params['ignore_list'] = []
            window['FILTER'].Update('')
            window['IGNORE_FILTER'].Update('')
            window['APPLY_FILTER'].Update(disabled=True)
            window['CLEAR_FILTER'].Update(disabled=True)
            log_reload(values)

        if event == 'DEL_FILTER':
            log_reload(values)

        if event == 'TOUCH':
            touch = await asyncio.create_subprocess_shell(f"touch {values['SQUIRE_OUT_PATH']}", stdin=PIPE, stdout=PIPE,
                                                          stderr=STDOUT)
            await touch.wait()

        await asyncio.sleep(0)


async def async_main():
    # window.refresh()
    loop = asyncio.get_event_loop()
    request_queue = asyncio.Queue()
    data_queue = asyncio.Queue()
    pong_queue = asyncio.Queue()
    outcome_queue = asyncio.Queue()
    updates_list = []

    processor_task = loop.create_task(message_processor(data_queue, pong_queue, updates_list))
    # asyncio.run_coroutine_threadsafe(message_processor(data_queue, pong_queue, updates_list), loop)

    # ping_task = loop.create_task(ping(request_queue, pong_queue, data_queue, outcome_queue))
    asyncio.run_coroutine_threadsafe(ping(request_queue, pong_queue, data_queue, outcome_queue), loop)

    # handler_task = loop.create_task(client_handler_wrapper(
    #                   request_queue, data_queue, outcome_queue, send_request, receive_data, loop))
    asyncio.run_coroutine_threadsafe(client_handler_wrapper(
                      request_queue, data_queue, outcome_queue, send_request, receive_data, loop), loop)

    # close_task = loop.create_task(close_connection(outcome_queue, request_queue, data_queue))
    asyncio.run_coroutine_threadsafe(close_connection(outcome_queue, request_queue, data_queue), loop)

    semaphore_task = loop.create_task(semaphore_manager(semaphore, window))
    # asyncio.run_coroutine_threadsafe(semaphore_manager(semaphore, window), loop)

    window_task = loop.create_task(window_update(request_queue, data_queue, pong_queue, outcome_queue, loop))
    # asyncio.run_coroutine_threadsafe(window_update(request_queue, data_queue, pong_queue, outcome_queue, loop), loop)
    # window_routine = asyncio.to_thread(window_update, request_queue, data_queue, pong_queue, outcome_queue, loop)
    # asyncio.run_coroutine_threadsafe(window_routine, loop)
    # await asyncio.gather(ping_task, close_task, semaphore_task)

    # await processor_task

    # while True:
    #     await asyncio.sleep(1)

    # window.close()

    await asyncio.gather(processor_task, window_task, semaphore_task)


# The GUI elements are all declared in synchronous main(), since they only need to be declared once
if __name__ == "__main__":
    layout = [
        [Sg.TabGroup([
            [Sg.Tab('Controls',
                    [space(),
                     [
                         Sg.Frame('Connection', [
                             input_field('Host', 'localhost', length=15),
                             input_field('Port', '1230', length=5),
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
                             [Sg.Input(size=(25, 1), default_text='out.txt', key='SQUIRE_OUT_PATH',
                                       enable_events=True)],
                             [Sg.FileBrowse(key='SQUIRE_OUT_BROWSE',
                                            file_types=[("Text Files", '*.txt'), ("All Files", '.*')],
                                            initial_folder=os.getcwd(),
                                            tooltip="Browse for a Squire output file",
                                            target=(-1, 0)),
                              Sg.Button(button_text="Touch", key='TOUCH',
                                        tooltip="Touch the squire output file to begin execution")], space()
                         ])],
                     ])],
            [Sg.Tab('Parameters',
                    [space(),
                     [
                         Sg.Text('Path to parameter file'),
                         Sg.Input(size=(25, 1), default_text='params.json', key='PARAMS_PATH',
                                  enable_events=True),
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
                         input_field('Parameter') + input_field('Value') +
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
            [Sg.Tab('Status',
                    [space(),
                     [Sg.Text()]
                     ])],
            [Sg.Tab('Log',
                    [space(),
                     input_field('Log file path', key='LOG_PATH') +
                     [Sg.FileBrowse(key='LOG_BROWSE',
                                    file_types=[("LOG Files", '*.log'), ('Text Files', '*.txt'),
                                                ("All Files", '.*')],
                                    initial_folder=os.getcwd(), tooltip="Browse for a log file")] +
                     [Sg.Button(button_text="Load", key='LOG_LOAD', disabled=True,
                                tooltip="Load the log file at the selected path"), checkmark('LOG_CHECK')],
                     [Sg.Multiline(pad=(10, 10), key='LOG', size=(130, 30), autoscroll=True)],
                     [Sg.Frame('Log Filters', [
                         input_field('Include item', key='FILTER') + input_field('Ignore list',
                                                                                 key='IGNORE_FILTER', length=88),
                         [Sg.Checkbox('Live Update', key='LIVE_UPDATE', disabled=True)] +
                         [Sg.Checkbox('Remove Filtered Text', key='DEL_FILTER', enable_events=True)] +
                         [Sg.Button(button_text="Apply", key='APPLY_FILTER', disabled=True,
                                    tooltip="Apply the entered filter to the log")] +
                         [Sg.Button(button_text="Clear", key='CLEAR_FILTER', disabled=True,
                                    tooltip="Clear the filter")]
                     ])]
                     ])],
            [Sg.Tab('Results',
                    [space(),
                     [Sg.Text()]
                     ])]
        ])],
        # [Sg.HSeparator()],
        [Sg.StatusBar('\t\t\t\t\t\t\t\t\t', key='STATUS'), indicator('CONNECTION_LIGHT', color='Black')[0]],
    ]

    # Declare the GUI window
    window = Sg.Window("Ceruleus Client", layout, resizable=True, finalize=True)

    asyncio.run(async_main())
