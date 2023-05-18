from datetime import datetime
from modules.config import params


# Some timestamp generators
def long_date():
    now = datetime.now()
    yield f"""{now.strftime('%A')}, {now.strftime('%B')} {now.strftime('%d')}, {now.strftime('%Y')}"""


def time():
    now = datetime.now()
    yield f"""{now.strftime('%H')}:{now.strftime('%M')}:{now.strftime('%S')}"""


def log_date_time():
    yield f"{next(long_date())}, {next(time())}: "


# Log printing function with options
def print_v(item, verbose_flag=True, out_handle=params['script_name'], timestamp=True):
    prefix = f"[{out_handle}] "
    if timestamp:
        prefix += next(log_date_time())
    if verbose_flag:
        print(prefix + str(item))
