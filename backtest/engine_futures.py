from dataclasses import dataclass
from typing import Dict, List
import pandas as pd


@dataclass
class FuturesTrade:
    symbol: str
    side: str               # "long" or "short"
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    qty: float
    pnl: float
    return_pct: float
    reason: str


class FuturesBacktestEngine:
    """
    USDT-M Futures Backtesting Engine
    - Isolated margin
    - Long + Short
    - Funding fee simulation
    - Liquidation-aware
    """

    def __init__(
        self,
        initial_equity: float,
        leverage: float = 2.0,
        fee_rate: float = 0.0004,        # 0.04% taker
        funding_rate: float = 0.0001,    # 0.01% per 8h (approx)
        funding_interval_bars: int = 32, # 8h on 15m candles
        max_open_positions: int = 3,
    ):
        self.initial_equity = initial_equity
        self.cash = initial_equity
        self.equity = initial_equity

        self.leverage = leverage
        self.fee_rate = fee_rate
        self.funding_rate = funding_rate
        self.funding_interval_bars = funding_interval_bars
        self.max_open_positions = max_open_positions

        self.open_positions: Dict[str, dict] = {}
        self.latest_prices: Dict[str, float] = {}

        self.trades: List[FuturesTrade] = []
        self.equity_curve: List[float] = []

    # ------------------------------------------------
    # Utilities
    # ------------------------------------------------

    def _apply_fee(self, notional: float) -> float:
        return notional * self.fee_rate

    def _mark_to_market(self):
        pos_value = 0.0
        for symbol, pos in self.open_positions.items():
            price = self.latest_prices.get(symbol)
            if price is None:
                continue

            direction = 1 if pos["side"] == "long" else -1
            pos_value += direction * (price - pos["entry_price"]) * pos["qty"]
            pos_value += pos["margin"]

        self.equity = self.cash + pos_value

    # ------------------------------------------------
    # Position Management
    # ------------------------------------------------

    def open_position(
        self,
        *,
        symbol: str,
        side: str,
        entry_price: float,
        stop_price: float,
        qty: float,
        margin_required: float,
        liquidation_price: float,
        timestamp,
        max_hold_bars: int,
    ):
        if len(self.open_positions) >= self.max_open_positions:
            return

        if margin_required > self.cash:
            return

        self.cash -= margin_required

        self.open_positions[symbol] = {
            "side": side,
            "entry_price": entry_price,
            "stop_price": stop_price,
            "qty": qty,
            "margin": margin_required,
            "liq_price": liquidation_price,
            "bars_held": 0,
            "max_hold_bars": max_hold_bars,
        }

    def close_position(self, symbol, exit_price, timestamp, reason):
        pos = self.open_positions.pop(symbol)

        direction = 1 if pos["side"] == "long" else -1
        pnl = direction * (exit_price - pos["entry_price"]) * pos["qty"]

        notional = pos["qty"] * exit_price
        fee = self._apply_fee(notional)

        self.cash += pos["margin"] + pnl - fee

        return_pct = pnl / pos["margin"]

        self.trades.append(
            FuturesTrade(
                symbol=symbol,
                side=pos["side"],
                entry_time=None,
                exit_time=timestamp,
                entry_price=pos["entry_price"],
                exit_price=exit_price,
                qty=pos["qty"],
                pnl=pnl - fee,
                return_pct=return_pct,
                reason=reason,
            )
        )

    # ------------------------------------------------
    # Candle Handler
    # ------------------------------------------------

    def on_candle(self, symbol, candle, signal=None):
        timestamp = candle.name
        high = candle["high"]
        low = candle["low"]
        close = candle["close"]

        self.latest_prices[symbol] = close

        # ----- Manage open positions -----
        if symbol in self.open_positions:
            pos = self.open_positions[symbol]
            pos["bars_held"] += 1

            # Liquidation check
            if pos["side"] == "long" and low <= pos["liq_price"]:
                self.close_position(symbol, pos["liq_price"], timestamp, "liquidation")

            elif pos["side"] == "short" and high >= pos["liq_price"]:
                self.close_position(symbol, pos["liq_price"], timestamp, "liquidation")

            # Stop loss
            elif pos["side"] == "long" and low <= pos["stop_price"]:
                self.close_position(symbol, pos["stop_price"], timestamp, "stop")

            elif pos["side"] == "short" and high >= pos["stop_price"]:
                self.close_position(symbol, pos["stop_price"], timestamp, "stop")

            # Time stop
            elif pos["bars_held"] >= pos["max_hold_bars"]:
                self.close_position(symbol, close, timestamp, "time")

            # Funding fee
            elif pos["bars_held"] % self.funding_interval_bars == 0:
                funding_fee = pos["qty"] * close * self.funding_rate
                self.cash -= funding_fee

        # ----- Open new position -----
        if signal and symbol not in self.open_positions:
            self.open_position(
                symbol=symbol,
                side=signal.side,
                entry_price=signal.entry_price,
                stop_price=signal.stop_loss,
                qty=signal.qty,
                margin_required=signal.margin_required,
                liquidation_price=signal.liquidation_price,
                timestamp=timestamp,
                max_hold_bars=signal.max_hold_bars,
            )

        self._mark_to_market()
        self.equity_curve.append(self.equity)

    # ------------------------------------------------
    # Results
    # ------------------------------------------------

    def results(self) -> pd.DataFrame:
        if not self.trades:
            return pd.DataFrame()
        return pd.DataFrame([t.__dict__ for t in self.trades])
