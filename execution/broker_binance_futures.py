import ccxt
import os
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=BASE_DIR / ".env")


class BinanceFuturesBroker:
    """
    Live Binance USDT-M Futures execution broker.
    - Isolated margin
    - Market entry
    - Stop-market + take-profit-market exits
    """

    def __init__(self):
        #testnet = os.getenv("BINANCE_FUTURES_TESTNET", "false").lower() == "true"

        self.exchange = ccxt.binance({
            "apiKey": os.getenv("BINANCE_API_KEY"),
            "secret": os.getenv("BINANCE_API_SECRET"),
            "enableRateLimit": True,
            "options": {
                "defaultType": "future",
            },
        })

        #if testnet:
           # self.exchange.set_sandbox_mode(True)

        self.exchange.load_markets()

    # ------------------------------------------------
    # Configuration
    # ------------------------------------------------

    def set_isolated_margin(self, symbol: str):
        try:
            self.exchange.set_margin_mode("isolated", symbol)
        except Exception:
            pass  # already set

    def set_leverage(self, symbol: str, leverage: int):
        self.exchange.set_leverage(leverage, symbol)

    # ------------------------------------------------
    # Orders
    # ------------------------------------------------

    def place_entry(
        self,
        *,
        symbol: str,
        side: str,           # "long" or "short"
        qty: float,
    ):
        order_side = "buy" if side == "long" else "sell"

        return self.exchange.create_order(
            symbol=symbol,
            type="market",
            side=order_side,
            amount=qty,
        )

    def place_stop_loss(
        self,
        *,
        symbol: str,
        side: str,
        qty: float,
        stop_price: float,
    ):
        close_side = "sell" if side == "long" else "buy"

        return self.exchange.create_order(
            symbol=symbol,
            type="stop_market",
            side=close_side,
            amount=qty,
            params={
                "stopPrice": self.exchange.price_to_precision(symbol, stop_price),
                "closePosition": True,
                "workingType": "MARK_PRICE",
            },
        )

    def place_take_profit(
        self,
        *,
        symbol: str,
        side: str,
        qty: float,
        take_profit: float,
    ):
        close_side = "sell" if side == "long" else "buy"

        return self.exchange.create_order(
            symbol=symbol,
            type="take_profit_market",
            side=close_side,
            amount=qty,
            params={
                "stopPrice": self.exchange.price_to_precision(symbol, take_profit),
                "closePosition": True,
                "workingType": "MARK_PRICE",
            },
        )

    # ------------------------------------------------
    # Emergency
    # ------------------------------------------------

    def emergency_close(self, symbol: str, side: str, qty: float):
        close_side = "sell" if side == "long" else "buy"

        return self.exchange.create_order(
            symbol=symbol,
            type="market",
            side=close_side,
            amount=qty,
            params={"reduceOnly": True},
        )
