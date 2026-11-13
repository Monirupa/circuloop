import joblib, shap
from prep import load, FEATURES, TARGET

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def phrase(name, v):
    if name == "lag1":    return f"usage 15 minutes ago ({v:.1f} kWh)"
    if name == "lag4":    return f"usage 1 hour ago ({v:.1f} kWh)"
    if name == "lag96":   return f"usage at this time yesterday ({v:.1f} kWh)"
    if name == "roll4":   return f"average usage over the last hour ({v:.1f} kWh)"
    if name == "hour":    return f"the time of day ({int(v):02d}:{int((v % 1) * 60):02d})"
    if name == "dow":     return f"the day ({DAYS[int(v)]})"
    if name == "weekend": return "it being a weekend" if v else "it being a weekday"

def narrate(pred, base, contribs, values, n=2, mae=None):
    direction = "above" if pred > base else "below"
    ranked = sorted(zip(FEATURES, contribs, values), key=lambda t: -abs(t[1]))[:n]
    parts = [f"{phrase(nm, v)} ({c:+.1f} kWh)" for nm, c, v in ranked]
    text = (f"Expected usage for the next 15 minutes is {pred:.1f} kWh, "
            f"{abs(pred - base):.1f} kWh {direction} the typical {base:.1f} kWh. "
            f"Main drivers: " + "; ".join(parts) + ".")
    if mae:
        text += f" Typical model error is about +/-{mae:.1f} kWh."
    return text
