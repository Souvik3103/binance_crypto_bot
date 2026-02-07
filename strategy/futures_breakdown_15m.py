from dataclasses import dataclass
import pandas as pd
import numpy as np


@dataclass
class FuturesSignal:
    symbol: str
    side: str                 # "long" or "short"
    entry_price: float
    stop_loss: float
    atr: float
    qty: float
    margin_required: float
    liquidation_price: float
    max_hold_bars: int


class FuturesBreakdown15m:
    """
    Bi-directional volatility breakdown strategy for USDT-M futures.
    All sizing is delegated to FuturesRiskManager.
    """

    def __init__(
        self,
        donchian_period: int = 20,
        ema_period: int = 50,
        atr_period: int = 14,
        min_atr_pct: float = 0.004,     # 0.4%
        stop_atr_mult: float = 1.0,
        tp_atr_mult: float = 2.0,
        max_hold_bars: int = 24,        # 6 hours on 15m
    ):
        self.donchian_period = donchian_period
        self.ema_period = ema_period
        self.atr_period = atr_period
        self.min_atr_pct = min_atr_pct
        self.stop_atr_mult = stop_atr_mult
        self.tp_atr_mult = tp_atr_mult
        self.max_hold_bars = max_hold_bars

    # ------------------------------------------------
    # Indicators
    # ------------------------------------------------

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # EMA
        df["ema"] = df["close"].ewm(span=self.ema_period, adjust=False).mean()

        # Donchian channels (shifted to avoid lookahead)
        df["donchian_high"] = (
            df["high"]
            .rolling(self.donchian_period)
            .max()
            .shift(1)
        )
        df["donchian_low"] = (
            df["low"]
            .rolling(self.donchian_period)
            .min()
            .shift(1)
        )

        # ATR
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(self.atr_period).mean()

        return df

    # ------------------------------------------------
    # Signal Generation
    # ------------------------------------------------

    def generate_signal(
        self,
        *,
        symbol: str,
        df: pd.DataFrame,
        position_open: bool,
        risk_manager,
        equity: float,
        open_positions: dict,
    ) -> FuturesSignal | None:
        """
        Strategy proposes a trade.
        Risk manager decides if it is allowed and sizes it.
        """

        if position_open:
            return None

        if len(df) < max(self.donchian_period, self.ema_period, self.atr_period) + 5:
            return None

        df = self.compute_indicators(df)
        cur = df.iloc[-1]

        if pd.isna(cur["atr"]) or pd.isna(cur["donchian_high"]) or pd.isna(cur["donchian_low"]):
            return None

        # Volatility filter
        if cur["atr"] / cur["close"] < self.min_atr_pct:
            return None

        entry_price = cur["close"]
        atr = cur["atr"]

        # ---------------- LONG BREAKOUT ----------------
        if entry_price > cur["donchian_high"] and entry_price > cur["ema"]:
            stop_price = entry_price - self.stop_atr_mult * atr

            decision = risk_manager.approve_trade(
                equity=equity,
                symbol=symbol,
                side="long",
                entry_price=entry_price,
                stop_price=stop_price,
                atr=atr,
                open_positions=open_positions,
            )

            if not decision.approved:
                return None

            return FuturesSignal(
                symbol=symbol,
                side="long",
                entry_price=entry_price,
                stop_loss=stop_price,
                atr=atr,
                qty=decision.position_size,
                margin_required=decision.margin_required,
                liquidation_price=decision.liquidation_price,
                max_hold_bars=self.max_hold_bars,
            )

        # ---------------- SHORT BREAKDOWN ----------------
        if entry_price < cur["donchian_low"] and entry_price < cur["ema"]:
            stop_price = entry_price + self.stop_atr_mult * atr

            decision = risk_manager.approve_trade(
                equity=equity,
                symbol=symbol,
                side="short",
                entry_price=entry_price,
                stop_price=stop_price,
                atr=atr,
                open_positions=open_positions,
            )

            if not decision.approved:
                return None

            return FuturesSignal(
                symbol=symbol,
                side="short",
                entry_price=entry_price,
                stop_loss=stop_price,
                atr=atr,
                qty=decision.position_size,
                margin_required=decision.margin_required,
                liquidation_price=decision.liquidation_price,
                max_hold_bars=self.max_hold_bars,
            )

        return None
