import numpy as np
import pandas as pd


def compute_metrics(trades: pd.DataFrame, equity_curve: list, initial_equity: float):
    if trades.empty:
        return {}

    returns = trades["return_pct"]
    equity = np.array(equity_curve)

    max_dd = np.max(np.maximum.accumulate(equity) - equity) / initial_equity

    metrics = {
        "trades": len(trades),
        "win_rate": (returns > 0).mean(),
        "avg_win": returns[returns > 0].mean(),
        "avg_loss": returns[returns < 0].mean(),
        "profit_factor": returns[returns > 0].sum() / abs(returns[returns < 0].sum()),
        "max_drawdown": max_dd,
        "final_equity": equity[-1],
        "return_pct": (equity[-1] - initial_equity) / initial_equity,
    }

    return metrics
