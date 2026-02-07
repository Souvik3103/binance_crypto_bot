from dataclasses import dataclass
import pandas as pd
import numpy as np


@dataclass
class Signal:
    symbol: str
    side: str
    entry_price: float
    stop_loss: float
    take_profit: float
    max_hold_bars: int


class VolatilityBreakout15m:
    def __init__(
        self,
        donchian_period: int = 20,
        atr_period: int = 14,
        min_atr_pct: float = 0.003,   # 0.3%
        stop_atr_mult: float = 1.0,
        tp_atr_mult: float = 2.0,
        max_hold_bars: int = 24,      # 6 hours
    ):
        self.donchian_period = donchian_period
        self.atr_period = atr_period
        self.min_atr_pct = min_atr_pct
        self.stop_atr_mult = stop_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.max_hold_bars = max_hold_bars

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        df["donchian_high"] = (
            df["high"]
            .rolling(self.donchian_period)
            .max()
            .shift(1)
        )

        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(self.atr_period).mean()

        return df

    def generate_signal(
        self,
        symbol: str,
        df: pd.DataFrame,
        position_open: bool,
    ) -> Signal | None:
        if position_open:
            return None

        if len(df) < max(self.donchian_period, self.atr_period) + 5:
            return None

        df = self.compute_indicators(df)
        cur = df.iloc[-1]

        # Breakout condition
        if pd.isna(cur["donchian_high"]):
            return None

        if cur["close"] <= cur["donchian_high"]:
            return None

        # Volatility filter
        if cur["atr"] / cur["close"] < self.min_atr_pct:
            return None

        entry = cur["close"]
        stop = entry - self.stop_atr_mult * cur["atr"]
        tp = entry + self.tp_atr_mult * cur["atr"]

        if stop <= 0 or tp <= entry:
            return None

        return Signal(
            symbol=symbol,
            side="buy",
            entry_price=entry,
            stop_loss=stop,
            take_profit=tp,
            max_hold_bars=self.max_hold_bars,
        )
