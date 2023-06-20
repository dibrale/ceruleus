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

unassigned_template = {
        'task': 'unassigned',
        'start': next(make_now()),
        'stop': next(make_now())
    }

data_list = [unassigned_template]


def make_figure(data_frame: pd.DataFrame) -> bytes:
    fig = px.timeline(data_frame, x_start="start", x_end="stop", y="task", color="task")
    return fig.to_image()


async def update_data(queue: asyncio.Queue):
    while True:
        await asyncio.sleep(0)
        new_data = await queue.get()
        time_stop = datetime.now()

        if new_data == {'update': 0}:
            data_list[-1].update({'stop': time_stop})
            continue
        await asyncio.sleep(0)

        if 'start' in new_data.keys() and new_data['task'] != data_list[-1]['task']:
            time_start = datetime.fromtimestamp(new_data['start'])
            if 'stop' in new_data.keys():
                time_stop = datetime.fromtimestamp(new_data['stop'])
            new_data.update({'start': time_start, 'stop': time_stop, 'task': new_data['task']})
            data_list.append(new_data)
            continue
        await asyncio.sleep(0)

        if 'stop' in new_data.keys():

            if 'start' not in new_data.keys() and new_data['task'] == data_list[-1]['task']:
                time_stop = datetime.fromtimestamp(new_data['stop'])
                data_list[-1].update({'stop': time_stop})

            data_list.append(unassigned_template)
            await asyncio.sleep(0)

