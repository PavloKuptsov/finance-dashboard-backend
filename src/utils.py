import os
from calendar import monthrange
from datetime import datetime, timedelta
from typing import Optional

from src.config import DATA_PATH


def get_latest_db_file():
    return max([f.path for f in os.scandir(DATA_PATH) if f.path.endswith('.bak')])


def timeframe_to_dates(year: int,
                       month: Optional[int] = None,
                       day: Optional[int] = None) -> tuple[datetime, datetime]:
    if day:
        d_from = datetime(year, month, day)
        d_to = d_from + timedelta(days=1)
    elif month:
        if month == 12:
            d_from = datetime(year, month, 1)
            d_to = datetime(year + 1, 1, 1)
        else:
            d_from = datetime(year, month, 1)
            d_to = datetime(year, month + 1, 1)
    else:
        d_from = datetime(year, 1, 1)
        d_to = datetime(year + 1, 1, 1)

    return d_from, d_to


def timeframe_to_timestamps(year: int,
                            month: Optional[int] = None,
                            day: Optional[int] = None) -> tuple[int, int]:
    dates = timeframe_to_dates(year, month, day)
    return int(dates[0].timestamp()), int(dates[1].timestamp())


def savings_separators(year: int, month: Optional[int]):
    separators = {}
    if month:
        _, days = monthrange(year, month)
        for day in range(1, days + 1):
            d = datetime(year, month, day, 0, 0, 0)
            if d > datetime.now():
                break

            separators[d.strftime('%d')] = d.timestamp()
    else:
        for month in range(1, 13):
            d = datetime(year, month, 1, 0, 0, 0)
            if d > datetime.now():
                break

            separators[d.strftime('%b %d')] = d.timestamp()

        separators['Dec 31'] = datetime(year + 1, 1, 1, 0, 0, 0).timestamp()

    return separators
