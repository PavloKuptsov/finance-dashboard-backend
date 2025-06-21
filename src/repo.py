from calendar import monthrange
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func, Integer, text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import PREPARATORY_QUERIES_FILE
from .dataclasses import CashFlowMonth, TF, BurnRateDay, BurnRateMonth, CategoryAmount, Category, Account, Transaction
from .models import AccountModel, Currency, CategoryModel, TransactionModel, TransactionType, CategoryType, \
    BalanceHistoryModel, DailyBalanceHistoryModel, DailyAccountCashflowModel
from .utils import timeframe_to_timestamps, savings_separators


async def get_accounts(db: AsyncSession, with_archived=False, currency_id=None):
    q = select(AccountModel).order_by(AccountModel.show_order)
    if not with_archived:
        q = q.where(AccountModel.is_archived.is_(with_archived))
    if currency_id:
        q = q.where(AccountModel.currency_id == currency_id)
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
    q_expenses = (select(func.sum(TransactionModel.homogenized_amount))
                  .where(TransactionModel.type == TransactionType.EXPENSE)
                  .where(TransactionModel.timestamp >= _from)
                  .where(TransactionModel.timestamp < _to)
                  .where(TransactionModel.is_scheduled.is_(False)))
    q_incomes = (select(func.sum(TransactionModel.destination_amount))
                 .where(TransactionModel.type == TransactionType.INCOME)
                 .where(TransactionModel.timestamp >= _from)
                 .where(TransactionModel.timestamp < _to)
                 .where(TransactionModel.is_scheduled.is_(False)))
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

    q = get_query(TransactionModel.homogenized_amount, TransactionType.EXPENSE)
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
               func.sum(TransactionModel.homogenized_amount))
            .where(TransactionModel.type == TransactionType.EXPENSE)
            .where(TransactionModel.timestamp >= _from)
            .where(TransactionModel.timestamp < _to)
            .where(TransactionModel.is_scheduled.is_(False))
    )

    q_raw = q_base.group_by(timeframe)
    res_raw = await db.execute(q_raw)
    result_raw = [i._tuple() for i in res_raw]
    dict_raw = {res[key]: res for res in result_raw}
    if not dict_raw:
        return {}

    date_range = range(min(dict_raw.keys()) if dict_raw.keys() else 1,
                       max(dict_raw.keys()) + 1 if dict_raw.keys() else 13)

    q_adjusted = q_base.where(func.abs(TransactionModel.homogenized_amount) < threshold).group_by(timeframe)
    res_adjusted = await db.execute(q_adjusted)
    result_adjusted = [i._tuple() for i in res_adjusted]
    dict_adjusted = {res[key]: res for res in result_adjusted}

    burn_rate_dict = {}
    for i in date_range:
        item = dict_raw.get(i)
        if timeframe ==TF.DAY:
            if item:
                adjusted_for_day = dict_adjusted.get(item[2])
                adjusted_total = adjusted_for_day[3] if adjusted_for_day else None
                br_period = BurnRateDay(year=item[0],
                                        month=item[1],
                                        day=item[2],
                                        raw_total=item[3],
                                        adjusted_total=adjusted_total)
            else:
                br_period = BurnRateDay(year=year, month=month, day=i, raw_total=None, adjusted_total=None)
            burn_rate_dict[br_period.label] = br_period
        else:
            if item:
                adjusted_for_month = dict_adjusted.get(item[1])
                adjusted_total = adjusted_for_month[3] if adjusted_for_month else None
                br_period = BurnRateMonth(year=item[0],
                                          month=item[1],
                                          raw_total=item[3],
                                          adjusted_total=adjusted_total)
            else:
                br_period = BurnRateMonth(year=year, month=month, raw_total=None, adjusted_total=None)
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
                func.sum(TransactionModel.homogenized_amount),
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
        .order_by(TransactionModel.homogenized_amount.desc())
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
            amount=tr.homogenized_amount,
            notes=tr.comment
        ))
    return transactions


async def get_savings(db: AsyncSession, year: int):
    _from, _to = timeframe_to_timestamps(year)
    separators = savings_separators(year)
    accounts = await get_accounts(db, currency_id=10051)
    account_names = {acc.id: acc.name for acc in accounts}
    colors = {acc.name: acc.color for acc in accounts}
    colors['Total'] = 16777215

    q = (
        select(BalanceHistoryModel)
        .where(BalanceHistoryModel.timestamp >= _from)
        .where(BalanceHistoryModel.timestamp < _to)
        .where(BalanceHistoryModel.account_id.in_(account_names.keys()))
        .order_by(BalanceHistoryModel.timestamp.asc())
    )

    res = await db.execute(q)
    balance_histories = res.scalars().all()
    bh_per_account = {acc_id: {} for acc_id in account_names}
    for bh in balance_histories:
        bh_per_account[bh.account_id][bh.timestamp] = bh.balance

    starting_balances = {}
    for acc_id in account_names:
        q = (
            select(BalanceHistoryModel.balance)
            .where(BalanceHistoryModel.account_id == acc_id)
            .where(BalanceHistoryModel.timestamp < _from)
            .order_by(BalanceHistoryModel.timestamp.desc())
            .limit(1)
        )
        res = await db.execute(q)
        starting_balances[acc_id] = res.scalar() or 0

    labels = []
    balances = {acc_name: [] for acc_name in account_names.values()}
    balances['Total'] = []
    for sep, timestamp in separators.items():
        labels.append(sep)
        total = 0
        for acc_id, acc_name in account_names.items():
            timestamps = [ts for ts in bh_per_account[acc_id].keys() if ts <= timestamp]
            max_ts = max(timestamps) if timestamps else None
            balance = bh_per_account[acc_id][max_ts] if max_ts else starting_balances[acc_id]
            balances[acc_name].append(balance)
            total += balance

        balances['Total'].append(total)
    change = balances['Total'][-1] - balances['Total'][0]

    return {'labels': labels,
            'colors': colors,
            'data': balances,
            'change': change}


async def prepare_data(db: AsyncSession):
    version_query = await db.execute(text('PRAGMA user_version;'))
    version = version_query.scalar()
    if version < 99:
        print('Translating the DB')
        with open(PREPARATORY_QUERIES_FILE) as f:
            for stmt in f.read().split('\n\n'):
                await db.execute(text(stmt))
        await db.commit()

        print('Compiling balance history')
        await compile_balances_history(db)
        print('Compiling daily balance history')
        await compile_daily_balance_history(db)
        print('Compiling daily cashflow')
        await compile_daily_cashflow(db)


async def compile_balances_history(db: AsyncSession):
    accounts = await get_accounts(db, with_archived=True)
    latest_balances = {acc.id: acc.starting_balance or 0 for acc in accounts}

    q = (
        select(TransactionModel)
        .where(TransactionModel.is_scheduled.is_(False))
        .order_by(TransactionModel.timestamp.asc())
    )
    res = await db.execute(q)
    transactions = res.scalars().all()
    for trans in transactions:
        if trans.type == TransactionType.INCOME:
            latest_balances[trans.account_id] += trans.amount
            history = BalanceHistoryModel(account_id=trans.account_id,
                                          transaction_id=trans.id,
                                          timestamp=trans.timestamp,
                                          balance=round(latest_balances[trans.account_id], 2))
            db.add(history)
        elif trans.type == TransactionType.EXPENSE:
            latest_balances[trans.account_id] -= trans.amount
            history = BalanceHistoryModel(account_id=trans.account_id,
                                          transaction_id=trans.id,
                                          timestamp=trans.timestamp,
                                          balance=round(latest_balances[trans.account_id], 2))
            db.add(history)
        else:
            latest_balances[trans.account_id] -= trans.amount
            latest_balances[trans.destination_id] += trans.destination_amount
            history1 = BalanceHistoryModel(account_id=trans.account_id,
                                           transaction_id=trans.id,
                                           timestamp=trans.timestamp,
                                           balance=round(latest_balances[trans.account_id], 2))
            history2 = BalanceHistoryModel(account_id=trans.destination_id,
                                           transaction_id=trans.id,
                                           timestamp=trans.timestamp,
                                           balance=round(latest_balances[trans.destination_id], 2))
            db.add(history1)
            db.add(history2)

        await db.flush()

    await db.commit()


async def get_latest_balance_for_account_to_date(db: AsyncSession, account_id: int, timestamp: int):
    q = (
        select(BalanceHistoryModel.balance)
        .where(BalanceHistoryModel.account_id == account_id)
        .where(BalanceHistoryModel.timestamp <= timestamp)
        .order_by(BalanceHistoryModel.id.desc())
        .limit(1)
    )
    res = await db.execute(q)
    return res.scalar()


async def get_first_transaction_timestamp(db: AsyncSession) -> datetime:
    q = (
        select(func.min(TransactionModel.timestamp))
        .where(TransactionModel.is_scheduled.is_(False))
    )
    res = await db.execute(q)
    return datetime.fromtimestamp(res.scalar())


async def compile_daily_balance_history(db: AsyncSession):
    accounts = await get_accounts(db, with_archived=True)
    accounts_in_balance = {acc.id: acc for acc in accounts if acc.is_in_balance}

    min_datetime = await get_first_transaction_timestamp(db) + timedelta(days=1)
    current_datetime = datetime(min_datetime.year, min_datetime.month, min_datetime.day)

    while current_datetime < datetime.now() + timedelta(days=1):
        balance = 0
        timestamp = int(current_datetime.timestamp())
        for acc in accounts_in_balance:
            change = await get_latest_balance_for_account_to_date(db, acc, timestamp)
            if change:
                balance += change

        history = DailyBalanceHistoryModel(timestamp=timestamp, balance=round(balance, 2))
        db.add(history)
        await db.flush()

        current_datetime += timedelta(days=1)

    await db.commit()


async def get_daily_balance_history(db: AsyncSession, year: int, month: Optional[int]):
    _from, _to = timeframe_to_timestamps(year, month)
    q = (
        select(DailyBalanceHistoryModel)
        .where(DailyBalanceHistoryModel.timestamp >= _from)
        .where(DailyBalanceHistoryModel.timestamp <= _to)
        .order_by(DailyBalanceHistoryModel.timestamp.asc())
    )

    res = await db.execute(q)
    daily_balance_histories = res.scalars().all()

    labels = [datetime.fromtimestamp(bal.timestamp).day for bal in daily_balance_histories]
    data = [bal.balance for bal in daily_balance_histories]

    return {'labels': labels, 'data': data}


async def compile_daily_cashflow(db: AsyncSession):
    accounts = await get_accounts(db)

    min_datetime = await get_first_transaction_timestamp(db)
    current_datetime = datetime(min_datetime.year, min_datetime.month, min_datetime.day)

    while current_datetime < datetime.now() + timedelta(days=1):
        previous_timestamp = int((current_datetime - timedelta(days=1)).timestamp())
        current_timestamp = int(current_datetime.timestamp())
        q = (
            select(TransactionModel)
            .where(TransactionModel.timestamp >= previous_timestamp)
            .where(TransactionModel.timestamp < current_timestamp)
            .where(TransactionModel.is_scheduled.is_(False))
        )

        res = await db.execute(q)
        transactions = res.scalars().all()

        for acc in accounts:
            incomes = [trans.amount for trans in transactions
                       if trans.account_id == acc.id and trans.type == TransactionType.INCOME]
            expenses = [trans.amount for trans in transactions
                        if trans.account_id == acc.id and trans.type == TransactionType.EXPENSE]
            transfers_from = [trans.amount for trans in transactions
                              if trans.account_id == acc.id and trans.type == TransactionType.TRANSFER]
            transfers_to = [trans.destination_amount for trans in transactions
                            if trans.destination_id == acc.id and trans.type == TransactionType.TRANSFER]

            inflow = round(sum(incomes) + sum(transfers_to), 2)
            outflow = round(sum(expenses) + sum(transfers_from), 2)

            if inflow or outflow:
                cashflow = DailyAccountCashflowModel(timestamp=previous_timestamp,
                                                     account_id=acc.id,
                                                     inflow=inflow,
                                                     outflow=outflow)
                db.add(cashflow)
                await db.flush()

        current_datetime += timedelta(days=1)
    await db.commit()


async def get_account_cashflow(db: AsyncSession, year: int, month: Optional[int]):
    _from, _to = timeframe_to_timestamps(year, month)
    q = (
        select(
            DailyAccountCashflowModel.account_id,
            func.sum(DailyAccountCashflowModel.inflow),
            func.sum(DailyAccountCashflowModel.outflow),
        )
        .where(DailyAccountCashflowModel.timestamp >= _from)
        .where(DailyAccountCashflowModel.timestamp <= _to)
        .group_by(DailyAccountCashflowModel.account_id)
    )

    res = await db.execute(q)
    rows = [i._tuple() for i in res]

    cashflows = {}
    for row in rows:
        cashflows[row[0]] = {'inflow': row[1], 'outflow': row[2]}

    return cashflows
