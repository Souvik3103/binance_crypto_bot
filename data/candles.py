from pathlib import Path
import ccxt
import pandas as pd
import time


DATA_DIR = Path("data/cache")
DATA_DIR.mkdir(parents=True, exist_ok=True)


class CandleLoader:
    def __init__(self, exchange, timeframe: str = "1h", limit: int = 1000):
        self.exchange = exchange
        self.timeframe = timeframe
        self.limit = limit

    def _cache_path(self, symbol: str) -> Path:
        fname = symbol.replace("/", "_")
        return DATA_DIR / f"{fname}_{self.timeframe}.csv"

    def load(
        self,
        symbol: str,
        since: int | None = None,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        path = self._cache_path(symbol)

        if path.exists() and not force_refresh:
            df = pd.read_csv(path, parse_dates=["timestamp"], index_col="timestamp")
            return df.sort_index()

        all_candles = []
        since_ts = since

        while True:
            candles = self.exchange.fetch_ohlcv(
                symbol,
                timeframe=self.timeframe,
                since=since_ts,
                limit=self.limit,
            )

            if not candles:
                break

            all_candles.extend(candles)
            since_ts = candles[-1][0] + 1

            if len(candles) < self.limit:
                break

            time.sleep(self.exchange.rateLimit / 1000)

        df = pd.DataFrame(
            all_candles,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )

        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        df = df[~df.index.duplicated(keep="first")]
        df.sort_index(inplace=True)

        df.to_csv(path)
        return df
