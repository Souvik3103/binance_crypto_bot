import ccxt
import pandas as pd

#from strategy.ema_atr_trend import EMATRTrendStrategy
#from strategy.ema_mean_reversion_15m import EMAMeanReversion15m
from strategy.volatility_breakout_15m import VolatilityBreakout15m
from backtest.engine import BacktestEngine
from backtest.metrics import compute_metrics
from data.candles import CandleLoader


INITIAL_EQUITY = 10_000  # simulate ₹10k
SYMBOLS = ["BTC/USDT", "ETH/USDT"]
TIMEFRAME = "15m"


def main():
    exchange = ccxt.binance({
        "enableRateLimit": True,
        "options": {"defaultType": "spot"},
    })

    loader = CandleLoader(exchange, timeframe=TIMEFRAME)
    #strategy = EMATRTrendStrategy()
    #strategy = EMAMeanReversion15m()
    strategy = VolatilityBreakout15m()
    engine = BacktestEngine(
        initial_equity=INITIAL_EQUITY,
        risk_per_trade=0.004,
        fee_rate=0.001,
        slippage_bps=5,
    )

    # Load candles
    data = {}
    for symbol in SYMBOLS:
        df = loader.load(symbol)
        data[symbol] = df

    # Align on common timestamps
    common_index = data[SYMBOLS[0]].index
    for symbol in SYMBOLS[1:]:
        common_index = common_index.intersection(data[symbol].index)

    common_index = common_index.sort_values()

    WARMUP_BARS = 300
    # Candle-by-candle simulation
    for ts in common_index[WARMUP_BARS:]:  # skip warmup
        for symbol in SYMBOLS:
            df_slice = data[symbol].loc[:ts].tail(300)

            signal = strategy.generate_signal(
                symbol=symbol,
                df=df_slice,
                position_open=(symbol in engine.open_positions),
            )

            engine.on_candle(
                symbol=symbol,
                candle=data[symbol].loc[ts],
                signal=signal,
            )

    trades = engine.results()
    metrics = compute_metrics(trades, engine.equity_curve, INITIAL_EQUITY)

    print("\n=== BACKTEST RESULTS ===")
    for k, v in metrics.items():
        print(f"{k}: {v}")

    print("\nFinal equity:", engine.equity)


if __name__ == "__main__":
    main()
