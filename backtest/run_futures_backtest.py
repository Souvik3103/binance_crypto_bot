import ccxt
import pandas as pd

from data.candles import CandleLoader
from risk.risk_futures import FuturesRiskManager
from backtest.engine_futures import FuturesBacktestEngine
from strategy.futures_breakdown_15m import FuturesBreakdown15m


# ---------------- CONFIG ----------------

INITIAL_EQUITY = 10_000  # simulate ₹10k
TIMEFRAME = "15m"
WARMUP_BARS = 300

SYMBOLS = [
    "BTC/USDT",
    "ETH/USDT",
    "BNB/USDT",
    "SOL/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "AVAX/USDT",
    "LINK/USDT",
]


# ---------------- RUNNER ----------------

def main():
    exchange = ccxt.binance({
        "enableRateLimit": True,
        "options": {
            "defaultType": "future",   # USDT-M futures
        },
    })

    loader = CandleLoader(exchange, timeframe=TIMEFRAME)
    risk_manager = FuturesRiskManager()
    engine = FuturesBacktestEngine(
        initial_equity=INITIAL_EQUITY,
        leverage=2.0,
    )
    strategy = FuturesBreakdown15m()

    # -------- Load candles --------
    data = {}
    for symbol in SYMBOLS:
        df = loader.load(symbol)
        data[symbol] = df

    # -------- Align timestamps --------
    common_index = data[SYMBOLS[0]].index
    for symbol in SYMBOLS[1:]:
        common_index = common_index.intersection(data[symbol].index)
    common_index = common_index.sort_values()

    assert len(common_index) > WARMUP_BARS + 50, "Not enough data"

    # -------- Initialize drawdown tracking --------
    risk_manager.reset_daily(INITIAL_EQUITY)
    risk_manager.reset_weekly(INITIAL_EQUITY)

    # -------- Candle-by-candle simulation --------
    for ts in common_index[WARMUP_BARS:]:
        for symbol in SYMBOLS:
            candle = data[symbol].loc[ts]
            df_slice = data[symbol].loc[:ts].tail(400)

            # Drawdown kill-switch
            dd_check = risk_manager.check_drawdown(engine.equity)
            if not dd_check.approved:
                print("TRADING HALTED:", dd_check.reason)
                break

            signal = strategy.generate_signal(
                symbol=symbol,
                df=df_slice,
                position_open=(symbol in engine.open_positions),
                risk_manager=risk_manager,
                equity=engine.equity,
                open_positions=engine.open_positions,
            )

            engine.on_candle(
                symbol=symbol,
                candle=candle,
                signal=signal,
            )

    # -------- Results --------
    trades = engine.results()

    if trades.empty:
        print("No trades generated.")
        return

    returns = trades["return_pct"]

    metrics = {
        "trades": len(trades),
        "win_rate": (returns > 0).mean(),
        "avg_win": returns[returns > 0].mean(),
        "avg_loss": returns[returns < 0].mean(),
        "profit_factor": (
            returns[returns > 0].sum() / abs(returns[returns < 0].sum())
            if not returns[returns < 0].empty else float("inf")
        ),
        "max_drawdown": max(
            (max(engine.equity_curve[:i+1]) - engine.equity_curve[i])
            / max(engine.equity_curve[:i+1])
            for i in range(len(engine.equity_curve))
        ),
        "final_equity": engine.equity,
        "return_pct": (engine.equity - INITIAL_EQUITY) / INITIAL_EQUITY,
    }

    print("\n=== FUTURES BACKTEST RESULTS ===")
    for k, v in metrics.items():
        print(f"{k}: {v}")

    print("\nFinal equity:", engine.equity)


if __name__ == "__main__":
    main()
