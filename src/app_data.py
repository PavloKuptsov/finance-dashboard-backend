import httpx
from httpx import HTTPError
from sqlalchemy import select

from src.config import EXC_RATE_ENDPOINT
from src.models import Currency


example = {
    "date":"10.10.2024",
    "bank":"PB",
    "baseCurrency":980,
    "baseCurrencyLit":"UAH",
    "exchangeRate":[
        {"baseCurrency":"UAH","currency":"EUR","saleRateNB":45.1274000,"purchaseRateNB":45.1274000,"saleRate":45.7500000,"purchaseRate":44.7500000},
        {"baseCurrency":"UAH","currency":"GBP","saleRateNB":53.8933000,"purchaseRateNB":53.8933000,"saleRate":54.2200000,"purchaseRate":53.4400000},
        {"baseCurrency":"UAH","currency":"PLN","saleRateNB":10.4994000,"purchaseRateNB":10.4994000,"saleRate":10.5700000,"purchaseRate":10.4200000},
        {"baseCurrency":"UAH","currency":"USD","saleRateNB":41.1934000,"purchaseRateNB":41.1934000,"saleRate":41.4500000,"purchaseRate":40.8500000},
    ]
}

FALLBACK_RATES = {'UAH': 1, 'USD': 41.2, 'EUR': 45.5}


class AppData:
    def __init__(self):
        self.exchange_rates = {}

    async def get_exchange_rates(self, session):
        if self.exchange_rates:
            return self.exchange_rates

        q = select(Currency)
        result = await session.execute(q)
        currencies = result.scalars().all()
        try:
            api_response = httpx.get(EXC_RATE_ENDPOINT)
            api_response.raise_for_status()
            res = api_response.json()
            rates_dict = {}

            for curr in currencies:
                if curr.is_default:
                    rates_dict[curr.name_short] = 1
                else:
                    rates_dict[curr.name_short] = \
                        [pair for pair in res['exchangeRate'] if pair['currency'] == curr.name_short][0]['saleRateNB']
        except (HTTPError, IndexError):
            rates_dict = FALLBACK_RATES

        exchange_rates_matrix = {}
        for curr1 in currencies:
            exchange_rates_matrix[curr1.name_short] = {}
            for curr2 in currencies:
                exchange_rates_matrix[curr1.name_short][curr2.name_short] = (
                        rates_dict[curr1.name_short] / rates_dict[curr2.name_short])

        self.exchange_rates = exchange_rates_matrix
        return exchange_rates_matrix

app_data = AppData()
