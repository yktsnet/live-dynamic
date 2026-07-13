import json
import datetime

import pandas as pd

from lib import paths


def load_bars(warmup_days: int = 2) -> pd.DataFrame:
    bars_dir = paths.get_bars_dir()
    rows = []
    days_collected = 0
    today = datetime.date.today()
    current = today
    max_lookback = 30

    while days_collected <= warmup_days:
        if (today - current).days > max_lookback:
            break

        ym = current.strftime("%Y-%m")
        filename = current.strftime("%Y-%m-%d") + "_m5.jsonl"
        path = bars_dir / ym / filename

        if path.exists():
            day_rows = []
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        day_rows.append(json.loads(line))
                    except Exception:
                        continue

            rows = day_rows + rows
            days_collected += 1

        current -= datetime.timedelta(days=1)

    if not rows:
        raise ValueError("bars data not found")

    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["time_utc"])
    return df.set_index("time").sort_index()[["open", "high", "low", "close"]]
