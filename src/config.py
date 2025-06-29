from datetime import datetime


BURN_RATE_AMOUNT_THRESHOLD = 4000
MAX_TRANSACTION_AMOUNT_THRESHOLD = 1_000_000
DATA_PATH = '/app/data'
PREPARATORY_QUERIES_FILE = 'sql/preparatory_queries.sql'
PB_EXCHANGE_ENDPOINT = 'https://api.privatbank.ua/p24api/exchange_rates?json&date={}'
EXC_RATE_ENDPOINT = PB_EXCHANGE_ENDPOINT.format(datetime.now().strftime('%d.%m.%Y'))
