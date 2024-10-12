from datetime import datetime


AMOUNT_THRESHOLD = 4000
PREPARATORY_QUERIES_FILE = 'sql/preparatory_queries.sql'
PB_EXCHANGE_ENDPOINT = 'https://api.privatbank.ua/p24api/exchange_rates?json&date={}'
EXC_RATE_ENDPOINT = PB_EXCHANGE_ENDPOINT.format(datetime.now().strftime('%d.%m.%Y'))
