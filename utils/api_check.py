import ccxt
import os
from dotenv import load_dotenv

load_dotenv()

exchange = ccxt.binance({
    "apiKey": os.getenv("BINANCE_FUTURES_KEY"),
    "secret": os.getenv("BINANCE_FUTURES_SECRET"),
    "options": {"defaultType": "future"},
})

balance = exchange.fetch_balance({"type": "future"})
print(balance["total"]["USDT"])
