from dataclasses import dataclass
from typing import Dict, List
import pandas as pd


@dataclass
class Trade:
    symbol: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    qty: float
    pnl: float
    return_pct: float
    reason: str


class BacktestEngine:
    def __init__(
        self,
        initial_equity: float,
        risk_per_trade: float = 0.004,   # 0.4%
        fee_rate: float = 0.001,         # 0.1%
        slippage_bps: float = 5,         # 5 bps
        max_open_positions: int = 2,
        daily_dd_limit: float = 0.02,
    ):
        # Capital
        self.initial_equity = initial_equity
        self.cash = initial_equity
        self.equity = initial_equity

        # Risk
        self.risk_per_trade = risk_per_trade
        self.fee_rate = fee_rate
        self.slippage_bps = slippage_bps
        self.max_open_positions = max_open_positions
        self.daily_dd_limit = daily_dd_limit

        # State
        self.open_positions: Dict[str, dict] = {}
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = []
        self.latest_prices: Dict[str, float] = {}

        self.peak_equity = initial_equity
        self.trading_halted = False

    # ---------- Utilities ----------

    def _apply_slippage(self, price: float, side: str) -> float:
        slip = price * (self.slippage_bps / 10_000)
        return price + slip if side == "buy" else price - slip

    def _apply_fee(self, notional: float) -> float:
        return notional * self.fee_rate

    def _update_drawdown(self):
        self.peak_equity = max(self.peak_equity, self.equity)
        dd = (self.peak_equity - self.equity) / self.peak_equity
        if dd >= self.daily_dd_limit:
            self.trading_halted = True

    def _mark_to_market(self):
        pos_value = 0.0
        for symbol, pos in self.open_positions.items():
            if symbol not in self.latest_prices:
                continue
            pos_value += pos["qty"] * self.latest_prices[symbol]
        self.equity = self.cash + pos_value

    # ---------- Trading Logic ----------

    def open_position(self, signal, timestamp):
        if self.trading_halted:
            return

        if len(self.open_positions) >= self.max_open_positions:
            return

        if signal.symbol in self.open_positions:
            return

        stop_distance = signal.entry_price - signal.stop_loss
        if stop_distance <= 0:
            return

        risk_amount = self.equity * self.risk_per_trade
        qty = risk_amount / stop_distance

        entry_price = self._apply_slippage(signal.entry_price, "buy")
        cost = qty * entry_price
        fee = self._apply_fee(cost)

        if cost + fee > self.cash:
            return

        self.cash -= (cost + fee)

        self.open_positions[signal.symbol] = {
            "entry_price": entry_price,
            "stop_loss": signal.stop_loss,
            "take_profit": signal.take_profit,
            "qty": qty,
            "entry_time": timestamp,
            "bars_held": 0,
            "max_hold_bars": signal.max_hold_bars,
        }

    def close_position(self, symbol, price, timestamp, reason):
        pos = self.open_positions.pop(symbol)

        exit_price = self._apply_slippage(price, "sell")
        value = pos["qty"] * exit_price
        fee = self._apply_fee(value)

        self.cash += value - fee

        pnl = (exit_price - pos["entry_price"]) * pos["qty"] - fee
        return_pct = pnl / (pos["entry_price"] * pos["qty"])

        self.trades.append(
            Trade(
                symbol=symbol,
                entry_time=pos["entry_time"],
                exit_time=timestamp,
                entry_price=pos["entry_price"],
                exit_price=exit_price,
                qty=pos["qty"],
                pnl=pnl,
                return_pct=return_pct,
                reason=reason,
            )
        )

    # ---------- Candle Handler ----------

    def on_candle(self, symbol, candle, signal=None):
        timestamp = candle.name
        high = candle["high"]
        low = candle["low"]
        close = candle["close"]

        # Update price cache
        self.latest_prices[symbol] = close

        # Manage open position
        if symbol in self.open_positions:
            pos = self.open_positions[symbol]
            pos["bars_held"] += 1

            if low <= pos["stop_loss"]:
                self.close_position(symbol, pos["stop_loss"], timestamp, "stop")

            elif high >= pos["take_profit"]:
                self.close_position(symbol, pos["take_profit"], timestamp, "target")

            elif pos["bars_held"] >= pos["max_hold_bars"]:
                self.close_position(symbol, close, timestamp, "time")

        # Open new position
        if signal:
            self.open_position(signal, timestamp)

        # Mark to market & risk checks
        self._mark_to_market()
        self._update_drawdown()
        self.equity_curve.append(self.equity)

    # ---------- Results ----------

    def results(self) -> pd.DataFrame:
        if not self.trades:
            return pd.DataFrame()
        return pd.DataFrame([t.__dict__ for t in self.trades])
