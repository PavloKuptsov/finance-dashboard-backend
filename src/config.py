from datetime import datetime, timedelta

BURN_RATE_AMOUNT_THRESHOLD = 4000
MAX_TRANSACTION_AMOUNT_THRESHOLD = 1_000_000
DATA_PATH = '/app/data'
PREPARATORY_QUERIES_FILE = 'sql/preparatory_queries.sql'
EXCHANGE_RATE_DATE = datetime.now() if datetime.now().hour > 8 else datetime.now() - timedelta(days=1)
PB_EXCHANGE_ENDPOINT = 'https://api.privatbank.ua/p24api/exchange_rates?json&date={}'
EXC_RATE_ENDPOINT = PB_EXCHANGE_ENDPOINT.format(EXCHANGE_RATE_DATE.strftime('%d.%m.%Y'))
