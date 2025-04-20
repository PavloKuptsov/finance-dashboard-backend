from enum import IntEnum

from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey
from sqlalchemy.orm import relationship, Relationship

from .db import Base


class AccountType(IntEnum):
    ROUTINE = 0
    SAVINGS = 1
    SYSTEM = 4


class TransactionType(IntEnum):
    EXPENSE = 0
    INCOME = 1
    TRANSFER = 2


class CategoryType(IntEnum):
    INCOME = 0
    EXPENSE = 1


class Currency(Base):
    __tablename__ = 'currencies'
    id = Column(Integer, primary_key=True)
    name_short = Column(String)
    symbol = Column(String)
    is_default = Column(Boolean)


class AccountModel(Base):
    __tablename__ = 'accounts'
    id = Column(Integer, primary_key=True)
    type = Column(Integer)
    currency_id = Column(Integer, ForeignKey('currencies.id'))
    name = Column(String)
    starting_balance = Column(Float)
    balance = Column(Float)
    credit_limit = Column(Float)
    goal = Column(Float)
    is_in_balance = Column(Boolean)
    is_in_expenses = Column(Boolean)
    show_order = Column(Integer)
    icon_id = Column(Integer)
    color = Column(Integer)
    is_archived = Column(Boolean)

    currency = relationship(Currency, backref='accounts', lazy='joined')

    def __repr__(self):
        return f'<AccountModel(id={self.id}, name={self.name})>'


class CategoryModel(Base):
    __tablename__ = 'categories'
    id = Column(Integer, primary_key=True)
    type = Column(Integer)
    name = Column(String)
    icon_id = Column(Integer)
    color = Column(Integer)
    parent_category_id = Column(Integer, ForeignKey('categories.id'))

    # parent_category = Relationship('CategoryModel', lazy='joined')


class TransactionModel(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True)
    type = Column(Integer)
    timestamp = Column(Integer)
    currency_id = Column(Integer)
    account_id = Column(Integer)
    destination_id = Column(Integer, ForeignKey('categories.id'))
    amount = Column(Float)
    destination_amount = Column(Float)
    comment = Column(String)
    is_scheduled = Column(Boolean)

    category = relationship(CategoryModel, backref='parent', lazy='joined')

    def __repr__(self):
        return f'<TransactionModel(timestamp={self.timestamp}, amount={self.amount})>'


class BalanceHistoryModel(Base):
    __tablename__ = 'balance_history'
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer)
    transaction_id = Column(Integer)
    timestamp = Column(Integer)
    balance = Column(Float)


class DailyBalanceHistoryModel(Base):
    __tablename__ = 'daily_balance_history'
    id = Column(Integer, primary_key=True)
    timestamp = Column(Integer)
    balance = Column(Float)


class DailyAccountCashflowModel(Base):
    __tablename__ = 'daily_account_cashflow'
    id = Column(Integer, primary_key=True)
    timestamp = Column(Integer)
    account_id = Column(Integer)
    inflow = Column(Float)
    outflow = Column(Float)
