from dataclasses import dataclass
import pandas as pd
import numpy as np


@dataclass
class Signal:
    symbol: str
    side: str              # "buy" or "none"
    entry_price: float
    stop_loss: float
    take_profit: float
    atr: float


class EMATRTrendStrategy:
    def __init__(
        self,
        ema_fast: int = 50,
        ema_slow: int = 200,
        atr_period: int = 14,
        pullback_atr_frac: float = 0.5,
        stop_atr_mult: float = 1.5,
        tp_atr_mult: float = 3.0,
    ):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.atr_period = atr_period
        self.pullback_atr_frac = pullback_atr_frac
        self.stop_atr_mult = stop_atr_mult
        self.tp_atr_mult = tp_atr_mult

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        df columns required: ["open", "high", "low", "close"]
        """
        df = df.copy()

        df["ema_fast"] = df["close"].ewm(span=self.ema_fast, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.ema_slow, adjust=False).mean()

        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(self.atr_period).mean()

        return df

    def generate_signal(
        self,
        symbol: str,
        df: pd.DataFrame,
        position_open: bool,
    ) -> Signal | None:
        """
        Returns Signal or None
        """
        if position_open:
            return None

        df = self.compute_indicators(df)

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # Trend filter
        if latest["ema_fast"] <= latest["ema_slow"]:
            return None

        # Pullback condition
        pullback_distance = abs(latest["close"] - latest["ema_fast"])
        if pullback_distance > self.pullback_atr_frac * latest["atr"]:
            return None

        # Avoid entering on sharp momentum candles
        if latest["close"] > prev["close"] * 1.01:
            return None

        entry_price = latest["close"]
        atr = latest["atr"]

        stop_loss = entry_price - self.stop_atr_mult * atr
        take_profit = entry_price + self.tp_atr_mult * atr

        # Sanity check
        if stop_loss <= 0 or take_profit <= entry_price:
            return None

        return Signal(
            symbol=symbol,
            side="buy",
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            atr=atr,
        )
