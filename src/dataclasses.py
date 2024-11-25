from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Optional


class TF(StrEnum):
    YEAR = 'year'
    MONTH = 'month'
    DAY = 'day'


@dataclass
class CashFlowMonth:
    year: int
    month: int
    expense: float = 0
    income: float = 0

    @property
    def label(self):
        return f'{self.year}-{self.month:02}'


@dataclass
class BurnRateMonth:
    year: int
    month: int
    raw_total: Optional[float] = None
    adjusted_total: Optional[float] = None
    days: int = 0

    @property
    def label(self):
        return f'{self.year}-{self.month:02}'

    @property
    def raw(self):
        return self.raw_total / self.days

    @property
    def adjusted(self):
        return self.adjusted_total / self.days

    @property
    def not_over(self):
        today = datetime.today()
        return today.year == self.year and today.month == self.month


@dataclass
class BurnRateDay:
    year: int
    month: int
    day: int
    raw_total: Optional[float] = None
    adjusted_total: Optional[float] = None
    days: int = 1

    @property
    def label(self):
        return f'{self.day}'


@dataclass
class Category:
    id: int
    name: str
    color: int
    parent_category_id: int = None
    parent_category: 'Category' = None


@dataclass
class CategoryAmount:
    category: Category
    amount: float


@dataclass
class Account:
    id: int
    name: str


@dataclass
class Transaction:
    id: int
    date: int
    account: Account
    category: Category
    amount: float
    notes: str
