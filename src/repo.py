from calendar import monthrange
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func, Integer
from sqlalchemy.ext.asyncio import AsyncSession

from .dataclasses import CashFlowMonth, TF, BurnRateDay, BurnRateMonth, CategoryAmount, Category, Account, Transaction
from .models import AccountModel, Currency, CategoryModel, TransactionModel, TransactionType, CategoryType
from .utils import timeframe_to_timestamps


async def get_accounts(db: AsyncSession, with_archived=False):
    q = select(AccountModel).order_by(AccountModel.show_order)
    if not with_archived:
        q = q.where(AccountModel.is_archived.is_(with_archived))
    res = await db.execute(q)
    r = res.scalars().all()
    return r


async def get_accounts_dict(db: AsyncSession):
    res = await get_accounts(db, with_archived=True)
    accounts = {acc.id: Account(acc.id, acc.name) for acc in res}
    return accounts


async def get_currencies(db: AsyncSession):
    q = select(Currency)
    res = await db.execute(q)
    return res.scalars().all()


async def get_categories(db: AsyncSession):
    q = select(CategoryModel)
    res = await db.execute(q)
    return res.scalars().all()


async def get_categories_dict(db: AsyncSession, with_subcategories=False):
    res = await get_categories(db)
    categories =  {cat.id: Category(cat.id, cat.name, cat.color, cat.parent_category_id) for cat in res}

    if with_subcategories:
        for cat in categories.values():
            if cat.parent_category_id:
                cat.parent_category = categories[cat.parent_category_id]

    return categories


async def get_totals(db: AsyncSession, year: int, month: Optional[int]):
    _from, _to = timeframe_to_timestamps(year, month)
    q_expenses = (select(func.sum(TransactionModel.amount))
                  .where(TransactionModel.type == TransactionType.EXPENSE)
                  .where(TransactionModel.timestamp >= _from)
                  .where(TransactionModel.timestamp < _to))
    q_incomes = (select(func.sum(TransactionModel.destination_amount))
                 .where(TransactionModel.type == TransactionType.INCOME)
                 .where(TransactionModel.timestamp >= _from)
                 .where(TransactionModel.timestamp < _to))
    res_expenses = await db.execute(q_expenses)
    res_incomes = await db.execute(q_incomes)
    expenses = res_expenses.scalar()
    incomes = res_incomes.scalar()
    return {'sum_income': incomes, 'sum_expenses': expenses}


async def get_cashflow(db: AsyncSession, year: int, month: Optional[int]):
    _from, _to = timeframe_to_timestamps(year, month)

    def get_query(amount_field, transaction_type):
        fields = [
            func.cast(func.strftime('%Y', TransactionModel.timestamp, 'unixepoch', 'localtime'), Integer).label(TF.YEAR),
            func.cast(func.strftime('%m', TransactionModel.timestamp, 'unixepoch', 'localtime'), Integer).label(TF.MONTH),
            func.sum(amount_field)
        ]

        return (
            select(*fields)
            .where(TransactionModel.type == transaction_type)
            .where(TransactionModel.timestamp >= _from)
            .where(TransactionModel.timestamp < _to)
            .where(TransactionModel.is_scheduled.is_(False))
            .group_by(TF.MONTH)
            .order_by(TF.MONTH)
        )

    q = get_query(TransactionModel.destination_amount, TransactionType.INCOME)
    res = await db.execute(q)
    result_income = [i._tuple() for i in res]

    q = get_query(TransactionModel.amount, TransactionType.EXPENSE)
    res = await db.execute(q)
    result_expense = [i._tuple() for i in res]

    cashflow_dict = {}
    for item in result_expense:
        c_month = CashFlowMonth(*item)
        cashflow_dict[c_month.label] = c_month

    for item in result_income:
        c_month = CashFlowMonth(item[0], item[1], 0, item[2])
        if c_month.label in cashflow_dict:
            cashflow_dict[c_month.label].income = c_month.income
        else:
            cashflow_dict[c_month.label] = c_month

    return cashflow_dict


async def get_burn_rate(db: AsyncSession, year: int, month: Optional[int], threshold=4000):
    _from, _to = timeframe_to_timestamps(year, month)
    timeframe, key = (TF.DAY, 2) if month else (TF.MONTH, 1)


    q_base = (
        select(func.cast(func.strftime('%Y', TransactionModel.timestamp, 'unixepoch', 'localtime'), Integer).label(TF.YEAR),
               func.cast(func.strftime('%m', TransactionModel.timestamp, 'unixepoch', 'localtime'), Integer).label(TF.MONTH),
               func.cast(func.strftime('%d', TransactionModel.timestamp, 'unixepoch', 'localtime'), Integer).label(TF.DAY),
               func.sum(TransactionModel.amount))
            .where(TransactionModel.type == TransactionType.EXPENSE)
            .where(TransactionModel.timestamp >= _from)
            .where(TransactionModel.timestamp < _to)
            .where(TransactionModel.is_scheduled.is_(False))
    )

    q_raw = q_base.group_by(timeframe)
    res_raw = await db.execute(q_raw)
    result_raw = [i._tuple() for i in res_raw]
    dict_raw = {res[key]: res for res in result_raw}
    date_range = range(1, max(dict_raw.keys()) + 1)

    q_adjusted = q_base.where(func.abs(TransactionModel.amount) < threshold).group_by(timeframe)
    res_adjusted = await db.execute(q_adjusted)
    result_adjusted = [i._tuple() for i in res_adjusted]
    dict_adjusted = {res[key]: res for res in result_adjusted}

    burn_rate_dict = {}
    for i in date_range:
        item = dict_raw.get(i)
        if timeframe ==TF.DAY:
            if item:
                adjusted_for_day = dict_adjusted.get(item[2])
                adjusted_total = adjusted_for_day[3] if adjusted_for_day else 0
                br_period = BurnRateDay(year=item[0],
                                        month=item[1],
                                        day=item[2],
                                        raw_total=item[3],
                                        adjusted_total=adjusted_total)
            else:
                br_period = BurnRateDay(year=year, month=month, day=i, raw_total=0, adjusted_total=0)
            burn_rate_dict[br_period.label] = br_period
        else:
            if item:
                adjusted_for_month = dict_adjusted.get(item[1])
                adjusted_total = adjusted_for_month[3] if adjusted_for_month else 0
                br_period = BurnRateMonth(year=item[0],
                                          month=item[1],
                                          raw_total=item[3],
                                          adjusted_total=adjusted_total)
            else:
                br_period = BurnRateMonth(year=year, month=month, raw_total=0, adjusted_total=0)
            _, days = monthrange(br_period.year, br_period.month)
            br_period.days = datetime.today().day if br_period.not_over else days

        burn_rate_dict[br_period.label] = br_period

    return burn_rate_dict


async def get_subcategory_amounts(db: AsyncSession, year: int, month: Optional[int]):
    _from, _to = timeframe_to_timestamps(year, month)
    q = (select(CategoryModel.id,
                CategoryModel.name,
                CategoryModel.color,
                CategoryModel.parent_category_id,
                func.sum(TransactionModel.amount),
                ).join(TransactionModel)
         .where(TransactionModel.type == TransactionType.EXPENSE)
         .where(TransactionModel.timestamp >= _from)
         .where(TransactionModel.timestamp < _to)
         .where(TransactionModel.is_scheduled.is_(False))
         .where(CategoryModel.type == CategoryType.EXPENSE)
         .group_by(CategoryModel.name))
    res = await db.execute(q)
    result = [i._tuple() for i in res]

    category_amounts = []
    for item in result:
        cat = Category(*item[:-1])
        category_amounts.append(CategoryAmount(cat, item[-1]))
    category_amounts.sort(key=lambda x: x.amount, reverse=True)

    return category_amounts


async def get_category_amounts(db: AsyncSession, year: int, month: Optional[int]):
    _from, _to = timeframe_to_timestamps(year, month)
    subc_amounts = await get_subcategory_amounts(db, year, month)
    subc_dict = {item.category.id: item for item in subc_amounts}
    categories_dict = await get_categories_dict(db)


    for key in list(subc_dict.keys()):
        cat_amt = subc_dict[key]
        parent_id = cat_amt.category.parent_category_id
        if parent_id:
            if parent_id in subc_dict:
                subc_dict[parent_id].amount += cat_amt.amount
            else:
                cat = categories_dict[parent_id]
                subc_dict[parent_id] = CategoryAmount(cat, cat_amt.amount)
            del subc_dict[key]

    category_amounts = list(subc_dict.values())
    category_amounts.sort(key=lambda x: x.amount, reverse=True)

    return category_amounts


async def get_biggest_expenses(db: AsyncSession, year: int, month: Optional[int], limit: int = 30):
    _from, _to = timeframe_to_timestamps(year, month)
    categories = await get_categories_dict(db, with_subcategories=True)
    accounts = await get_accounts_dict(db)
    q = (
        select(TransactionModel)
        .where(TransactionModel.type == TransactionType.EXPENSE)
        .where(TransactionModel.timestamp >= _from)
        .where(TransactionModel.timestamp < _to)
        .where(TransactionModel.is_scheduled.is_(False))
        .order_by(TransactionModel.amount.desc())
        .limit(limit)
    )
    res = await db.execute(q)
    transactions_db = res.scalars().all()
    transactions = []
    for tr in transactions_db:
        transactions.append(Transaction(
            id=tr.id,
            date=tr.timestamp,
            account=accounts[tr.account_id],
            category=categories[tr.destination_id],
            amount=tr.amount,
            notes=tr.comment
        ))
    return transactions
