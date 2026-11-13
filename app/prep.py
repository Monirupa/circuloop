import pandas as pd

TARGET = "Usage_kWh"
FEATURES = ["hour", "dow", "weekend", "lag1", "lag4", "lag96", "roll4"]

def load():
    d = pd.read_csv("data/raw/Steel_industry_data.csv")
    d["date"] = pd.to_datetime(d["date"], dayfirst=True)
    d = d.sort_values("date").reset_index(drop=True)

    # calendar features
    d["hour"] = d["date"].dt.hour + d["date"].dt.minute / 60
    d["dow"] = d["date"].dt.day_of_week
    d["weekend"] = (d["dow"] >= 5).astype(int)

    # past usage only (shift moves values forward, so no future leakage)
    d["lag1"] = d[TARGET].shift(1)      # 15 min ago
    d["lag4"] = d[TARGET].shift(4)      # 1 hour ago
    d["lag96"] = d[TARGET].shift(96)    # same time yesterday
    d["roll4"] = d[TARGET].shift(1).rolling(4).mean()  # average of last hour

    return d.dropna().reset_index(drop=True)

if __name__ == "__main__":
    d = load()
    print(d.shape)
    print(d[["date", TARGET] + FEATURES].head())
