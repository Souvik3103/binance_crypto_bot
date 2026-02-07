from dataclasses import dataclass
from typing import Dict


@dataclass
class RiskDecision:
    approved: bool
    reason: str
    position_size: float | None = None
    margin_required: float | None = None
    liquidation_price: float | None = None


class FuturesRiskManager:
    """
    Futures risk manager for USDT-M, isolated margin, low leverage.
    This class is authoritative: if it rejects a trade, nothing overrides it.
    """

    def __init__(
        self,
        max_leverage: float = 2.0,
        risk_per_trade: float = 0.0015,      # 0.15%
        max_positions: int = 3,
        max_alloc_per_symbol: float = 0.30,  # 30% equity
        daily_drawdown_limit: float = 0.01,  # 1%
        weekly_drawdown_limit: float = 0.03, # 3%
        maintenance_margin_rate: float = 0.005,  # conservative
        liquidation_buffer_pct: float = 0.20,    # stop must be 20% away from liq
    ):
        self.max_leverage = max_leverage
        self.risk_per_trade = risk_per_trade
        self.max_positions = max_positions
        self.max_alloc_per_symbol = max_alloc_per_symbol
        self.daily_drawdown_limit = daily_drawdown_limit
        self.weekly_drawdown_limit = weekly_drawdown_limit
        self.maintenance_margin_rate = maintenance_margin_rate
        self.liquidation_buffer_pct = liquidation_buffer_pct

        self.start_of_day_equity = None
        self.start_of_week_equity = None

    # ------------------------------------------------------------------
    # Drawdown tracking
    # ------------------------------------------------------------------

    def reset_daily(self, equity: float):
        self.start_of_day_equity = equity

    def reset_weekly(self, equity: float):
        self.start_of_week_equity = equity

    def check_drawdown(self, equity: float) -> RiskDecision:
        # Guard against zero or invalid equity (DRY-RUN, empty account)
        if equity is None or equity <= 0:
            return RiskDecision(
                approved=True,
                reason="Equity zero or undefined (dry-run / empty account)",
            )

        if self.start_of_day_equity is not None and self.start_of_day_equity > 0:
            daily_dd = (
                self.start_of_day_equity - equity
            ) / self.start_of_day_equity

            if daily_dd >= self.daily_drawdown_limit:
                return RiskDecision(
                    approved=False,
                    reason="Daily drawdown limit breached",
                )

        if self.start_of_week_equity is not None and self.start_of_week_equity > 0:
            weekly_dd = (
                self.start_of_week_equity - equity
            ) / self.start_of_week_equity

            if weekly_dd >= self.weekly_drawdown_limit:
                return RiskDecision(
                    approved=False,
                    reason="Weekly drawdown limit breached",
                )

        return RiskDecision(approved=True, reason="Drawdown OK")

    # ------------------------------------------------------------------
    # Core risk approval
    # ------------------------------------------------------------------

    def approve_trade(
        self,
        *,
        equity: float,
        symbol: str,
        side: str,  # "long" or "short"
        entry_price: float,
        stop_price: float,
        atr: float,
        open_positions: Dict[str, dict],
    ) -> RiskDecision:
        """
        Returns RiskDecision with sizing + liquidation info if approved.
        """

        # ---- Global sanity ----
        if side not in ("long", "short"):
            return RiskDecision(False, "Invalid side")

        if len(open_positions) >= self.max_positions:
            return RiskDecision(False, "Max open positions reached")

        if symbol in open_positions:
            return RiskDecision(False, "Position already open on symbol")

        # ---- Stop distance ----
        stop_distance = abs(entry_price - stop_price)
        if stop_distance <= 0:
            return RiskDecision(False, "Invalid stop distance")

        # ---- Risk-based sizing ----
        risk_amount = equity * self.risk_per_trade
        position_size = risk_amount / stop_distance

        notional = position_size * entry_price
        margin_required = notional / self.max_leverage

        # ---- Allocation cap per symbol ----
        if margin_required > equity * self.max_alloc_per_symbol:
            return RiskDecision(False, "Per-symbol allocation cap exceeded")

        # ---- Liquidation price (isolated margin approximation) ----
        liquidation_price = self._calc_liquidation_price(
            entry_price=entry_price,
            side=side,
            leverage=self.max_leverage,
        )

        # ---- Liquidation safety check ----
        if side == "long":
            if liquidation_price >= stop_price * (1 + self.liquidation_buffer_pct):
                return RiskDecision(False, "Stop too close to liquidation")
        else:
            if liquidation_price <= stop_price * (1 - self.liquidation_buffer_pct):
                return RiskDecision(False, "Stop too close to liquidation")

        return RiskDecision(
            approved=True,
            reason="Trade approved",
            position_size=position_size,
            margin_required=margin_required,
            liquidation_price=liquidation_price,
        )

    # ------------------------------------------------------------------
    # Liquidation math
    # ------------------------------------------------------------------

    def _calc_liquidation_price(
        self,
        *,
        entry_price: float,
        side: str,
        leverage: float,
    ) -> float:
        """
        Conservative liquidation price estimate for isolated USDT-M futures.
        This intentionally underestimates safety to avoid edge cases.
        """

        if side == "long":
            return entry_price * (
                1 - (1 / leverage) + self.maintenance_margin_rate
            )
        else:
            return entry_price * (
                1 + (1 / leverage) - self.maintenance_margin_rate
            )
