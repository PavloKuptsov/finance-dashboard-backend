from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .app_data import app_data
from .db import get_db
from .repo import get_accounts, get_categories, get_currencies, get_totals, get_cashflow, get_burn_rate, \
    get_subcategory_amounts, get_category_amounts, get_biggest_expenses, get_savings, get_daily_balance_history, \
    get_account_cashflow

router = APIRouter()


@router.get('/accounts')
async def accounts(db: AsyncSession = Depends(get_db)):
    return await get_accounts(db)


@router.get('/currencies')
async def currencies(db: AsyncSession = Depends(get_db)):
    return await get_currencies(db)


@router.get('/categories')
async def categories(db: AsyncSession = Depends(get_db)):
    return await get_categories(db)


@router.get('/exchange_rates')
async def exchange_rates():
    return app_data.exchange_rates


@router.get('/totals')
async def totals(y: int, m: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    return await get_totals(db, y, m)


@router.get('/cashflow')
async def cashflow(y: int, m: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    return await get_cashflow(db, y, m)


@router.get('/burn_rate')
async def burn_rate(y: int, m: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    return await get_burn_rate(db, y, m)


@router.get('/subcategory_amounts')
async def subcategory_amounts(y: int, m: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    return await get_subcategory_amounts(db, y, m)


@router.get('/category_amounts')
async def category_amounts(y: int, m: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    return await get_category_amounts(db, y, m)


@router.get('/biggest_expenses')
async def biggest_expenses(y: int, m: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    return await get_biggest_expenses(db, y, m)


@router.get('/savings')
async def savings(y: int, db: AsyncSession = Depends(get_db)):
    return await get_savings(db, y)


@router.get('/daily_balances')
async def daily_balances(y: int, m: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    return await get_daily_balance_history(db, y, m)


@router.get('/account_cashflows')
async def account_cashflows(y: int, m: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    return await get_account_cashflow(db, y, m)
