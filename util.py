import datetime
from threading import current_thread


def log(msg: str, error: bool = False) -> None:
    print('{} - {} - {} {}'.format(
        str(datetime.datetime.time(datetime.datetime.now())),
        current_thread().getName(),
        "ERROR: " if error else "",
        msg
    ))


