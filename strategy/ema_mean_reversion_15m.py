from dataclasses import dataclass
import pandas as pd


@dataclass
class Signal:
    symbol: str
    side: str               # "buy"
    entry_price: float
    stop_loss: float
    take_profit: float
    max_hold_bars: int


class EMAMeanReversion15m:
    def __init__(
        self,
        ema_fast: int = 20,
        ema_slow: int = 50,
        min_pullback_pct: float = 0.004,   # 0.4%
        max_pullback_pct: float = 0.010,   # 1.0%
        stop_pct: float = 0.006,           # 0.6%
        tp_pct: float = 0.012,             # 1.2%
        max_hold_bars: int = 16,            # 4 hours on 15m
    ):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.min_pullback_pct = min_pullback_pct
        self.max_pullback_pct = max_pullback_pct
        self.stop_pct = stop_pct
        self.tp_pct = tp_pct
        self.max_hold_bars = max_hold_bars

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["ema_fast"] = df["close"].ewm(span=self.ema_fast, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.ema_slow, adjust=False).mean()
        return df

    def generate_signal(
        self,
        symbol: str,
        df: pd.DataFrame,
        position_open: bool,
    ) -> Signal | None:
        if position_open or len(df) < self.ema_slow + 5:
            return None

        df = self.compute_indicators(df)
        cur = df.iloc[-1]
        prev = df.iloc[-2]

        # Trend filter
        if cur["ema_fast"] < cur["ema_slow"]:
            return None

        # Pullback magnitude
        pullback_pct = (cur["ema_fast"] - cur["close"]) / cur["ema_fast"]
        if not (self.min_pullback_pct <= pullback_pct <= self.max_pullback_pct):
            return None

        # Avoid momentum dumps
        if cur["close"] < prev["close"] * 0.995:
            return None

        entry = cur["close"]
        stop = entry * (1 - self.stop_pct)
        tp = entry * (1 + self.tp_pct)

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
