import asyncio

import pandas as pd
import plotly.express as px
from datetime import datetime
import kaleido

from modules.logutils import make_now

sample_data = [
    dict(start='2021-01-01', stop='2021-02-28', task="Process 1"),
    dict(start='2021-03-01', stop='2021-04-15', task="Process 2"),
    dict(start='2021-04-15', stop='2021-05-30', task="Process 1")
]

sample_frame = pd.DataFrame(sample_data)


def unassigned_template():
    yield {
        'task': 'unassigned',
        'start': next(make_now()),
        'stop': next(make_now())
    }


# initial_frame = pd.DataFrame([unassigned_template])


def make_figure(data_frame: pd.DataFrame, mode='return', path='') -> bytes:
    fig = px.timeline(data_frame, x_start="start", x_end="stop", y="task", color="task", width=950, height=570, template='seaborn')
    fig.update_yaxes(title={'text': ''}, overwrite=True)
    # fig.update_xaxes(title={'text': 'Date and Time'}, overwrite=True)
    fig.update_legends(title={'text': 'Subtasks'}, overwrite=True)
    fig.update_layout(paper_bgcolor='lightsteelblue')
    if mode == 'write':
        fig.write_image(path, format=path.split('.')[-1])
    return fig.to_image('png')


async def update_data(queue: asyncio.Queue, data: list[dict]):
    while True:
        await asyncio.sleep(0)
        new_data = await queue.get()
        time_stop = datetime.now()

        if new_data == {'update': 0}:
            data[-1].update({'stop': time_stop})
            continue
        elif new_data == {'update': 1}:
            data.clear()
            data.append(next(unassigned_template()))
            continue
        await asyncio.sleep(0)

        if 'start' in new_data.keys() and new_data['task'] != data[-1]['task']:
            time_start = datetime.fromtimestamp(new_data['start'])
            if 'stop' in new_data.keys():
                time_stop = datetime.fromtimestamp(new_data['stop'])
            new_data.update({'start': time_start, 'stop': time_stop, 'task': new_data['task']})
            data.append(new_data)
            continue
        await asyncio.sleep(0)

        if 'stop' in new_data.keys():

            if 'start' not in new_data.keys() and new_data['task'] == data[-1]['task']:
                time_stop = datetime.fromtimestamp(new_data['stop'])
                data[-1].update({'stop': time_stop})

            data.append(next(unassigned_template()))
            await asyncio.sleep(0)

