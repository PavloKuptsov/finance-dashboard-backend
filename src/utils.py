import os
from datetime import datetime
from typing import Optional


def get_latest_db_file():
    return max([f.path for f in os.scandir('data') if f.path.endswith('.bak')])


def timeframe_to_dates(year: int, month: Optional[int] = None) -> tuple[datetime, datetime]:
    if month:
        d_from = datetime(year, month, 1)
        d_to = datetime(year, month + 1, 1)
    else:
        d_from = datetime(year, 1, 1)
        d_to = datetime(year + 1, 1, 1)

    return d_from, d_to


def timeframe_to_timestamps(year: int, month: Optional[int] = None) -> tuple[int, int]:
    dates = timeframe_to_dates(year, month)
    return int(dates[0].timestamp()), int(dates[1].timestamp())