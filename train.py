"""Train the energy forecasting model and compare it against two baselines.

Run from the project folder:   python train.py
Output: models/energy_model.joblib
"""
import sys
sys.path.insert(0, "app")

import joblib
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

from prep import load, FEATURES, TARGET

d = load()
cut = int(len(d) * 0.8)              # time-ordered split: train on the first 80%, test on the last 20%
train, test = d.iloc[:cut], d.iloc[cut:]
Xtr, ytr = train[FEATURES], train[TARGET]
Xte, yte = test[FEATURES], test[TARGET]


def report(name, pred):
    mae = mean_absolute_error(yte, pred)
    rmse = mean_squared_error(yte, pred) ** 0.5
    print(f"{name:28s} MAE={mae:6.3f}  RMSE={rmse:6.3f}")


report("Persistence (lag1)", test["lag1"])                       # baseline 1: same as 15 min ago
report("Linear regression", LinearRegression().fit(Xtr, ytr).predict(Xte))   # baseline 2

gbr = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, random_state=42)
gbr.fit(Xtr, ytr)
report("Gradient boosting", gbr.predict(Xte))                    # the model the app uses

joblib.dump(gbr, "models/energy_model.joblib")
print("saved models/energy_model.joblib")
