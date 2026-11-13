"""CircuLoop backend (FastAPI).

Run from the project folder:
    uvicorn main:app --reload --app-dir app

Pages and API
  /                   the dashboard (app/static/index.html, style.css, app.js)
  /api/overview       status numbers, insights and open actions
  /api/view/{id}      one plant section: text, figures, record checks, actions
  /api/flow           the factory flow map with live tonnes
  /api/series         actual vs forecast energy for a window of readings
  /api/hourly         typical daily load profile
  /api/explain/{i}    forecast, SHAP explanation and advice for reading i
  /api/scenario/{id}  what-if on one slag stream
  /api/graph          the knowledge graph as facts and nodes
  /api/chat           question answering (POST)

Everything here is ADVISORY. Nothing connects to plant equipment.
"""
import json
import os
from pathlib import Path

import joblib
import shap
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from networkx.readwrite import json_graph
from pydantic import BaseModel
from sklearn.metrics import mean_absolute_error

BASE = Path(__file__).resolve().parent.parent
os.chdir(BASE)  # prep.py reads data with relative paths

from prep import load, FEATURES, TARGET  # noqa: E402
from narrate import narrate  # noqa: E402
from content import SECTIONS, STEPS, FLOW_NODES, FLOW_EDGES, FLOW_DETAIL  # noqa: E402
import chat as chatbot  # noqa: E402

app = FastAPI(title="CircuLoop")
app.mount("/static", StaticFiles(directory=BASE / "app" / "static"), name="static")

# ------------------------------------------------------------------ startup
d = load()
cut = int(len(d) * 0.8)
train, test = d.iloc[:cut], d.iloc[cut:].reset_index(drop=True)
model = joblib.load(BASE / "models" / "energy_model.joblib")
test_pred = model.predict(test[FEATURES])
MODEL_MAE = float(mean_absolute_error(test[TARGET], test_pred))
PERSIST_MAE = float(mean_absolute_error(test[TARGET], test["lag1"]))
PEAK_KWH = float(test[TARGET].max())
# a small background keeps each SHAP explanation to about a second
explainer = shap.Explainer(model.predict, train[FEATURES].sample(30, random_state=0))
_explain_cache = {}

with open(BASE / "data" / "kg.json") as f:
    G = json_graph.node_link_graph(json.load(f), multigraph=True, directed=True)

TOLERANCE_PCT = 2.0   # assumed threshold for "records consistent"; tune later
DEVIATION_X = 2.0     # flag a reading when |actual - forecast| > 2 x typical error


# ------------------------------------------------------- knowledge graph helpers
def _qty(stream, rel, use=None):
    total = 0
    for u, v, e in list(G.out_edges(stream, data=True)) + list(G.in_edges(stream, data=True)):
        if e["relation"] == rel and (use is None or v == use):
            total += e["quantity_t"]
    return total


def stream_stats(stream):
    gen = _qty(stream, "PRODUCES")
    rec = _qty(stream, "ROUTED_TO", "Use:Recycled")
    sold = _qty(stream, "ROUTED_TO", "Use:Sold")
    gap_a = gen - rec - sold          # reading A: recycled is separate from sold
    gap_b = gen - sold                # reading B: recycled is already inside sold
    readings = []
    for label, gap in [("Recycled counted separately from sold", gap_a),
                       ("Recycled already included in sold", gap_b)]:
        pct = 100 * gap / gen
        readings.append({"reading": label, "gap_t": gap, "gap_pct": round(pct, 2),
                         "status": "OK" if abs(pct) <= TOLERANCE_PCT else "REVIEW"})
    status = "REVIEW" if any(r["status"] == "REVIEW" for r in readings) else "OK"
    return {"name": G.nodes[stream]["name"], "generated_t": gen, "recycled_t": rec,
            "sold_t": sold, "gap_a": gap_a, "gap_b": gap_b,
            "diversion_pct": round(100 * (rec + sold) / gen, 2),
            "diversion_if_included_pct": round(100 * sold / gen, 2),
            "recovery_pct": round(100 * rec / gen, 2),
            "excess_t": max(0, -gap_a),
            "readings": readings, "status": status}


def sid_stats(sid):
    return stream_stats(SECTIONS[sid]["stream"])


def section_actions(sid):
    s = sid_stats(sid)
    n = s["name"]
    acts = []

    def add(key, prio, text, why):
        acts.append({"id": f"{sid}-{key}", "priority": prio, "text": text, "why": why,
                     "steps": STEPS[key], "section": SECTIONS[sid]["name"], "section_id": sid})

    if s["status"] == "REVIEW":
        if s["gap_a"] < 0:
            add("reconcile", "high", f"Reconcile {n} records before using the indicators.",
                f"Recorded recycled + sold ({s['recycled_t'] + s['sold_t']:,} t) is more than the {s['generated_t']:,} t generated, "
                f"by {-s['gap_a']:,} t ({-100 * s['gap_a'] / s['generated_t']:.1f}%).")
            add("double", "medium", "Check whether recycled tonnes are also counted inside the sold figure.",
                f"If they are, the gap becomes {s['gap_b']:,} t ({100 * s['gap_b'] / s['generated_t']:.2f}% unaccounted for).")
            add("stock", "medium", "Check opening stock: slag sold this year may include stock from earlier years.",
                "Selling from an older stockpile makes dispositions exceed this year's generation.")
        else:
            add("gap", "high", f"Trace the unaccounted {n} tonnes.",
                f"{s['gap_a']:,} t ({100 * s['gap_a'] / s['generated_t']:.1f}%) has no recorded use.")
        add("provisional", "low", f"Treat {n} circularity indicators as provisional until the records are reconciled.",
            "The indicators are only as reliable as the underlying tonnage records.")
    else:
        add("monitor", "low", f"No action needed on {n} records. Keep monitoring.",
            f"Unrecorded share is {s['readings'][1]['gap_pct']}-{s['readings'][0]['gap_pct']}%, within the {TOLERANCE_PCT}% tolerance.")
        add("verify", "low", "Ask buyers to confirm end use, so 'sold' becomes 'verified use'.",
            "A sale is not the same as circular use. Confirmation turns the figure into evidence.")
    return acts


def all_actions():
    acts = section_actions("bf") + section_actions("bof")
    order = {"high": 0, "medium": 1, "low": 2}
    acts.sort(key=lambda a: order[a["priority"]])
    return acts


def build_insights():
    bf, bof = sid_stats("bf"), sid_stats("bof")
    out = []
    for s in (bf, bof):
        lo = min(r["gap_pct"] for r in s["readings"])
        hi = max(r["gap_pct"] for r in s["readings"])
        if s["status"] == "OK":
            out.append({"tone": "good", "title": f"{s['name']} records are consistent",
                        "text": f"{s['diversion_pct']}% of the {s['generated_t']:,} t generated is recorded as sold or recycled. "
                                f"Only {lo} to {hi}% is unaccounted for."})
        else:
            out.append({"tone": "warn", "title": f"{s['name']} records do not add up",
                        "text": f"Recorded recycled plus sold is {s['diversion_pct']}% of the tonnes generated. "
                                f"If recycled tonnes are already inside sold, {s['diversion_if_included_pct']}% is diverted and "
                                f"{s['gap_b']:,} t is unaccounted for."})
    out.append({"tone": "info", "title": "Where the loop is shortest",
                "text": f"In-plant recovery is {bof['recovery_pct']}% of LD slag but only {bf['recovery_pct']}% of BF slag. "
                        f"BF slag mostly leaves the plant through sales ({bf['diversion_if_included_pct']}%), so its circularity "
                        f"depends on buyers."})
    return out


def status_line():
    e = _latest["energy"] or {}
    n_review = sum(1 for sid in ("bf", "bof") if sid_stats(sid)["status"] == "REVIEW")
    parts = []
    if e:
        parts.append("The energy forecast is " + ("outside the expected range." if e["status"] == "CHECK" else "within the expected range.")
                     + f" Forecast {e['predicted_kwh']:.1f} kWh, actual {e['actual_kwh']:.1f} kWh.")
    parts.append(f"{n_review} of 2 by-product streams need a records review." if n_review
                 else "Both by-product streams have consistent records.")
    parts.append(f"{len([a for a in all_actions() if a['priority'] != 'low'])} higher-priority actions are open.")
    return " ".join(parts)


_latest = {"energy": None}   # the reading most recently explained, used by the chatbot

# --------------------------------------------------------------------- pages
@app.get("/")
def home():
    return FileResponse(BASE / "app" / "static" / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "test_rows": len(test)}


@app.get("/api/overview")
def overview():
    bf, bof = sid_stats("bf"), sid_stats("bof")
    return {
        "readings": len(test), "model_mae": round(MODEL_MAE, 2), "peak_kwh": PEAK_KWH,
        "bf": bf, "bof": bof,
        "review_count": sum(1 for s in (bf, bof) if s["status"] == "REVIEW"),
        "insights": build_insights(), "actions": all_actions(),
    }


@app.get("/api/view/{sid}")
def view(sid: str):
    if sid in SECTIONS:
        sec = SECTIONS[sid]
        s = sid_stats(sid)
        lo = min(r["gap_pct"] for r in s["readings"])
        hi = max(r["gap_pct"] for r in s["readings"])
        return {
            "id": sid, "title": sec["name"], "status": s["status"], "stream": s,
            "process": sec["process"], "how_circular": sec["how_circular"], "circular_note": sec["circular_note"],
            "stats": [
                {"label": f"{s['name']} generated", "value": f"{s['generated_t']:,}", "unit": "t", "basis": "OBSERVED"},
                {"label": "Recycled in plant", "value": f"{s['recycled_t']:,}", "unit": "t", "basis": "OBSERVED"},
                {"label": "Sold / dispatched", "value": f"{s['sold_t']:,}", "unit": "t", "basis": "OBSERVED"},
                {"label": "In-plant recovery", "value": f"{s['recovery_pct']}", "unit": "%", "basis": "DERIVED",
                 "note": "recycled / generated"},
                {"label": "Unrecorded share", "value": f"{lo} to {hi}", "unit": "%", "basis": "DERIVED",
                 "note": "range across the two readings"},
            ],
            "readings": s["readings"], "actions": section_actions(sid),
            "source": "Tata Steel Jamshedpur Form V FY2021-22",
        }
    if sid == "energy":
        return {
            "id": "energy", "title": "Plant energy", "status": "OK",
            "process": ("Electricity drawn by the plant, recorded every 15 minutes. Melting, rolling and auxiliary loads make "
                        "demand swing between light and heavy load through the day. The model forecasts the next 15-minute "
                        "reading from recent usage and the time of day, and flags readings that differ from the forecast by more "
                        f"than {DEVIATION_X:g} times the typical error."),
            "how_circular": "Recovering and reprocessing material also costs energy, so energy is part of the circularity picture.",
            "stats": [
                {"label": "Model error (MAE)", "value": f"{MODEL_MAE:.2f}", "unit": "kWh", "basis": "DERIVED",
                 "note": "time-ordered held-out 20% of the year"},
                {"label": "Baseline error (last value)", "value": f"{PERSIST_MAE:.2f}", "unit": "kWh", "basis": "DERIVED",
                 "note": "predict 'same as 15 min ago'"},
                {"label": "Improvement over baseline", "value": f"{100 * (1 - MODEL_MAE / PERSIST_MAE):.0f}", "unit": "%",
                 "basis": "DERIVED"},
                {"label": "Held-out readings", "value": f"{len(test):,}", "unit": "", "basis": "OBSERVED"},
            ],
            "readings": [], "actions": [],
            "source": "UCI Steel Industry Energy Consumption dataset (2018, 15-minute readings)",
        }
    raise HTTPException(404, "unknown section")


@app.get("/api/flow")
def flow():
    stats = {sid: sid_stats(sid) for sid in ("bf", "bof")}
    edges = []
    maxt = max(s["sold_t"] for s in stats.values())
    for e in FLOW_EDGES:
        e = dict(e)
        if "stream" in e:
            s = stats[e["stream"]]
            t = s["sold_t"] if e["use"] == "sold" else s["recycled_t"]
            e["t"] = t
            e["width"] = round(4 + 20 * t / maxt, 1)
            e["label"] = f"{e['label']} {t:,} t"
        edges.append(e)
    detail = {}
    for nid, info in FLOW_DETAIL.items():
        info = dict(info)
        info["data"] = []
        if nid in ("bfslag", "ldslag"):
            s = stats["bf" if nid == "bfslag" else "bof"]
            info["data"] = [
                {"label": "Generated", "value": f"{s['generated_t']:,} t", "basis": "OBSERVED"},
                {"label": "Sold / dispatched", "value": f"{s['sold_t']:,} t", "basis": "OBSERVED"},
                {"label": "Recycled in plant", "value": f"{s['recycled_t']:,} t", "basis": "OBSERVED"},
                {"label": "Diversion rate (recorded)", "value": f"{s['diversion_pct']}%", "basis": "DERIVED"},
                {"label": "Records", "value": s["status"], "basis": "DERIVED"},
            ]
        if nid == "raw":
            info["data"] = [
                {"label": "Iron ore", "value": "1,644 kg per tonne of steel", "basis": "OBSERVED"},
                {"label": "Coking coal", "value": "621 kg per tonne of steel", "basis": "OBSERVED"},
                {"label": "Limestone", "value": "319 kg per tonne of steel", "basis": "OBSERVED"},
                {"label": "Dolomite", "value": "130 kg per tonne of steel", "basis": "OBSERVED"},
            ]
        detail[nid] = info
    return {"nodes": FLOW_NODES, "edges": edges, "detail": detail,
            "source": "Quantities: Tata Steel Jamshedpur Form V FY2021-22. Routes without a figure describe typical practice."}


@app.get("/api/hourly")
def hourly():
    g = d.assign(h=d["hour"].astype(int)).groupby(["weekend", "h"])[TARGET].mean()
    return {"hours": list(range(24)),
            "weekday": [round(float(g.get((0, h), 0)), 1) for h in range(24)],
            "weekend": [round(float(g.get((1, h), 0)), 1) for h in range(24)]}


@app.get("/api/scenario/{sid}")
def scenario(sid: str, gen_change: float = 0, buyer_loss: float = 0, extra_recovery: float = 0):
    """What-if (impact modeling) on one stream. All three inputs are percentages.

    ASSUMPTIONS (shown to the user as ASSUMED):
      - uses the reading where recycled tonnes are already inside 'sold'
      - sales scale in proportion to generation
      - buyer_loss removes that share of sales
      - extra_recovery is the extra share of generation recovered in-plant
    """
    if sid not in SECTIONS:
        raise HTTPException(404, "unknown section")
    s = sid_stats(sid)
    gen0, sold0 = s["generated_t"], s["sold_t"]
    un0 = max(0, gen0 - sold0)
    gen1 = gen0 * (1 + gen_change / 100)
    sold1 = gen1 * (sold0 / gen0) * (1 - buyer_loss / 100)
    rec1 = gen1 * extra_recovery / 100
    un1 = max(0.0, gen1 - sold1 - rec1)

    def pack(gen, diverted, unmanaged, extra):
        return {"generated_t": round(gen), "sold_t": round(diverted), "extra_recovered_t": round(extra),
                "unmanaged_t": round(unmanaged), "diversion_pct": round(100 * (1 - unmanaged / gen), 2)}
    return {"stream": s["name"], "basis": "ASSUMED",
            "baseline": pack(gen0, sold0, un0, 0), "scenario": pack(gen1, sold1, un1, rec1),
            "assumptions": ["Recycled tonnes counted inside sold", "Sales scale with generation",
                            "Buyer loss removes that share of sales",
                            "Extra recovery is a share of generation processed in-plant"]}


@app.get("/api/series")
def series(end: int = 1000, n: int = 96):
    end = max(0, min(end, len(test) - 1))
    start = max(0, end - n + 1)
    return {
        "start": start, "end": end,
        "times": [str(t) for t in test["date"].iloc[start:end + 1]],
        "actual": [float(x) for x in test[TARGET].iloc[start:end + 1]],
        "predicted": [float(x) for x in test_pred[start:end + 1]],
    }


def _explain(i):
    i = max(0, min(i, len(test) - 1))
    if i in _explain_cache:
        return _explain_cache[i]
    row = test[FEATURES].iloc[[i]]
    sv = explainer(row)
    pred = float(test_pred[i])
    base = float(sv.base_values[0])
    actual = float(test[TARGET].iloc[i])
    dev = actual - pred
    flagged = abs(dev) > DEVIATION_X * MODEL_MAE

    actions = []

    def add(key, prio, text, why):
        actions.append({"id": f"energy-{key}-{i}", "priority": prio, "text": text, "why": why,
                        "steps": STEPS[key], "section": "Plant energy", "section_id": "energy"})

    if flagged:
        add("dev", "high", "Check for an unplanned equipment start or stop, or a meter fault.",
            f"Actual {actual:.1f} kWh differs from the forecast {pred:.1f} kWh by {abs(dev):.1f} kWh, more than "
            f"{DEVIATION_X:g} times the typical error ({MODEL_MAE:.1f} kWh).")
    if pred > 1.5 * base:
        add("high", "medium", "High load expected. Tell the shift supervisor and confirm the planned heats.",
            f"Forecast {pred:.1f} kWh is well above the typical {base:.1f} kWh.")
    if not actions:
        add("ok", "low", "Consumption is in the expected range. No action needed.",
            f"Actual and forecast differ by {abs(dev):.1f} kWh, within the normal error.")

    out = {
        "index": i, "time": str(test["date"].iloc[i]),
        "actual_kwh": actual, "predicted_kwh": pred, "baseline_kwh": base,
        "deviation_kwh": dev, "status": "CHECK" if flagged else "NORMAL",
        "contributions": {n: float(c) for n, c in zip(FEATURES, sv.values[0])},
        "values": {n: float(v) for n, v in zip(FEATURES, row.iloc[0].values)},
        "explanation": narrate(pred, base, sv.values[0], row.iloc[0].values, mae=MODEL_MAE),
        "actions": actions,
    }
    _explain_cache[i] = out
    return out


@app.get("/api/explain/{i}")
def explain(i: int):
    out = _explain(i)
    _latest["energy"] = out
    return out


@app.get("/api/graph")
def graph():
    names = {n: a.get("name", n) for n, a in G.nodes(data=True)}
    facts = []
    for u, v, e in G.edges(data=True):
        facts.append({
            "from": names[u], "relation": e["relation"], "to": names[v], "from_id": u, "to_id": v,
            "quantity_t": e.get("quantity_t"), "source": e.get("source"),
            "page": e.get("page"), "basis": e.get("basis"),
        })
    return {"nodes": [{"id": n, "type": a["type"], "name": a.get("name", n)} for n, a in G.nodes(data=True)],
            "facts": facts}


class ChatIn(BaseModel):
    message: str
    index: int = 1000


@app.post("/api/chat")
def chat(body: ChatIn):
    e = _explain(body.index)
    _latest["energy"] = e

    def run_scenario(sid, g, b, r):
        return scenario(sid, g, b, r)

    ctx = {"stream": sid_stats, "actions": lambda: all_actions() + e["actions"], "energy": e,
           "mae": MODEL_MAE, "persist_mae": PERSIST_MAE, "scenario": run_scenario, "status_line": status_line}
    return chatbot.answer(body.message.strip()[:300], ctx)
