"""Question answering for plant staff.

How it works (no external service, no API key):
  1. INTENT: the question is compared with example questions for each intent using TF-IDF vectors
     and cosine similarity (scikit-learn). The closest example decides the intent.
  2. ENTITIES: simple rules pick out which stream (BF slag or LD slag) is meant and any percentages.
  3. ANSWER: the answer is filled in from the live values passed in `ctx`. The bot never invents a
     number: if a value is not available it says so.

This is retrieval-based, not a generative model. To use a language model later, keep `classify` and
`entities`, and replace `answer` with a call that is given the same `ctx` values.
"""
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

INTENTS = {
    "overview": ["what is going on", "give me a summary", "how is the plant doing", "status of the plant",
                 "overall status", "what should I know right now", "plant overview", "any updates"],
    "energy_forecast": ["what is the energy forecast", "predicted energy use", "how much power will we use next",
                        "forecast for the next 15 minutes", "predicted electricity consumption", "expected load",
                        "what is the prediction"],
    "energy_why": ["why is the forecast high", "why is the forecast low", "explain the prediction",
                   "what drives the forecast", "what is causing this prediction", "explain the energy forecast",
                   "why does the model predict this"],
    "energy_check": ["is the reading normal", "is there an anomaly", "any alerts on energy", "is the actual different from forecast",
                     "is the energy use unusual", "was there a deviation", "is something wrong with the power reading"],
    "slag_status": ["how much slag is sold", "how much slag was generated", "how much slag is recycled",
                    "how much slag is diverted", "slag figures", "how much BF slag", "how much LD slag",
                    "slag tonnes", "how is slag being used"],
    "record_issue": ["why is the record flagged", "what is wrong with the records", "why is it marked review",
                     "why does LD slag need review", "records do not add up", "why is diversion over 100 percent",
                     "explain the review flag", "why are the numbers inconsistent", "why is LD slag flagged",
                     "why is slag flagged for review", "what is wrong with LD slag", "why is BF slag flagged", "what does review mean"],
    "unrecorded": ["how much slag is unaccounted for", "how much is missing", "what is the unrecorded share",
                   "where did the rest of the slag go", "is there any stockpile", "unknown fate share"],
    "actions": ["what should I do", "what are the recommended actions", "what are the next steps",
                "what needs attention", "what do you recommend", "what actions are open", "how do I fix this"],
    "scenario": ["what if the buyer stops buying", "what happens if slag output rises", "what if we recover more metal",
                 "what if we lose buyers", "simulate a change", "what if generation increases by 10 percent",
                 "what if sales drop", "scenario with extra recovery"],
    "improve": ["how can we improve circularity", "how can we recycle more", "how do we increase recovery",
                "how to reduce waste", "how to make the plant more circular", "ideas to improve diversion"],
    "model_accuracy": ["how accurate is the model", "what is the model error", "how good is the forecast",
                       "how reliable is the prediction", "what is the MAE", "can I trust the forecast"],
    "define": ["what is diversion rate", "what does diversion rate mean", "what is the diversion rate", "what does circularity mean", "what is circular economy",
               "what does unrecorded mean", "what is in-plant recovery", "define the indicators",
               "how is diversion calculated", "what does basis observed derived assumed mean"],
    "sources": ["where does the data come from", "what are the data sources", "which plant is this data from",
                "is this live data", "what data is used", "source of the numbers"],
    "help": ["help", "what can I ask", "what are your capabilities", "how do I use this", "examples of questions"],
    "greeting": ["hello", "hi", "hey", "good morning", "good evening"],
    "thanks": ["thanks", "thank you", "great thanks", "ok thank you"],
}

_examples, _labels = [], []
for _name, _qs in INTENTS.items():
    for _q in _qs:
        _examples.append(_q)
        _labels.append(_name)
_STOP = ["is", "the", "a", "an", "of", "to", "do", "we", "i", "me", "it", "this", "that", "are", "be", "at", "for", "in", "on",
         "and", "or", "does", "did", "can", "you", "my", "our", "there", "any"]
_vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, lowercase=True, stop_words=_STOP)
_X = _vec.fit_transform(_examples)

MIN_SCORE = 0.3


_GENERIC = {"what", "how", "why", "if", "which", "where", "who", "when"}
_VOCAB = set(_vec.vocabulary_)


def classify(text):
    words = [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w in _VOCAB and w not in _GENERIC and w not in _STOP]
    if not words:                      # nothing in the question is a topic word we know
        return None, 0.0
    sims = cosine_similarity(_vec.transform([text]), _X)[0]
    i = int(sims.argmax())
    return (_labels[i], float(sims[i])) if sims[i] >= MIN_SCORE else (None, float(sims[i]))


def streams_in(text):
    t = text.lower()
    bf = re.search(r"\b(bf|blast|granulated)\b", t)
    ld = re.search(r"\b(ld|bof|converter|steel slag)\b", t)
    if bf and not ld:
        return ["bf"]
    if ld and not bf:
        return ["bof"]
    return ["bf", "bof"]


def parse_scenario(text):
    """Return (gen_change, buyer_loss, extra_recovery) in percent, from a sentence like
    'what if we lose 30% of buyers'. Only the first percentage in the sentence is used."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent|per cent)", text.lower())
    if not m:
        return None
    n = float(m.group(1))
    t = text.lower()
    if re.search(r"recover|recycl|reuse|in-plant|in plant", t):
        return (0.0, 0.0, min(n, 30.0))
    if re.search(r"buyer|customer|sale|sales|sold|cement|stops? buying|drop out", t):
        return (0.0, min(n, 100.0), 0.0)
    sign = -1 if re.search(r"fall|decrease|lower|reduce|less|down|drop", t) else 1
    return (sign * min(n, 30.0), 0.0, 0.0)


SUGGEST = {
    "overview": ["Why is LD slag flagged?", "What should I do?", "Is the energy reading normal?"],
    "energy_forecast": ["Why is the forecast this value?", "Is the reading normal?", "How accurate is the model?"],
    "energy_why": ["Is the reading normal?", "How accurate is the model?"],
    "energy_check": ["Why is the forecast this value?", "What should I do?"],
    "slag_status": ["Why is LD slag flagged?", "How can we improve circularity?", "What if we lose 30% of buyers?"],
    "record_issue": ["What should I do?", "How much slag is unaccounted for?"],
    "unrecorded": ["Why is LD slag flagged?", "What should I do?"],
    "actions": ["Why is LD slag flagged?", "How can we improve circularity?"],
    "scenario": ["What if we recover 10% more LD slag?", "What if slag output rises 10%?"],
    "improve": ["What if we recover 10% more LD slag?", "What if we lose 30% of buyers?"],
    "model_accuracy": ["Why is the forecast this value?", "Where does the data come from?"],
    "define": ["How much slag is sold?", "Where does the data come from?"],
    "sources": ["What can I ask?", "Give me a summary"],
    "help": ["Give me a summary", "What should I do?", "What if we lose 30% of buyers?"],
    "greeting": ["Give me a summary", "What can I ask?"],
    "thanks": ["Give me a summary"],
    None: ["What can I ask?", "Give me a summary", "What should I do?"],
}


def _t(n):
    return f"{int(round(n)):,} t"


def answer(text, ctx):
    """ctx provides: stream(sid) -> stats dict, actions() -> list, energy -> dict, mae, persist_mae,
    scenario(sid, gen, buy, rec) -> dict, status_line() -> str."""
    intent, score = classify(text)
    out = {"intent": intent, "confidence": round(score, 2)}
    sids = streams_in(text)
    e = ctx["energy"]

    if intent is None:
        out["answer"] = ("I can answer questions about the energy forecast, slag records, circularity indicators, "
                         "recommended actions and what-if changes. I did not understand that one. Try one of the "
                         "suggestions below.")
    elif intent == "greeting":
        out["answer"] = "Hello. Ask me about the plant status, slag records, the energy forecast or what to do next."
    elif intent == "thanks":
        out["answer"] = "You're welcome."
    elif intent == "help":
        out["answer"] = ("You can ask, for example: 'Give me a summary', 'Is the energy reading normal?', "
                         "'Why is LD slag flagged?', 'How much BF slag is sold?', 'What should I do?', "
                         "'What if we lose 30% of buyers?' or 'What if we recover 10% more LD slag?'")
    elif intent == "overview":
        out["answer"] = ctx["status_line"]()
    elif intent == "energy_forecast":
        out["answer"] = (f"At {e['time']} the model forecasts {e['predicted_kwh']:.1f} kWh for the next 15 minutes. "
                         f"A typical reading is {e['baseline_kwh']:.1f} kWh and the actual reading is {e['actual_kwh']:.1f} kWh.")
    elif intent == "energy_why":
        out["answer"] = e["explanation"]
    elif intent == "energy_check":
        if e["status"] == "CHECK":
            out["answer"] = (f"No, it is not normal. The actual reading ({e['actual_kwh']:.1f} kWh) differs from the forecast "
                             f"({e['predicted_kwh']:.1f} kWh) by {abs(e['deviation_kwh']):.1f} kWh, more than twice the typical "
                             f"error of {ctx['mae']:.1f} kWh. Check for an unplanned equipment start or stop, or a meter fault.")
        else:
            out["answer"] = (f"The reading is normal. Actual ({e['actual_kwh']:.1f} kWh) and forecast ({e['predicted_kwh']:.1f} kWh) "
                             f"differ by {abs(e['deviation_kwh']):.1f} kWh, within the typical error of {ctx['mae']:.1f} kWh.")
    elif intent == "slag_status":
        lines = []
        for sid in sids:
            s = ctx["stream"](sid)
            lines.append(f"{s['name']}: {_t(s['generated_t'])} generated, {_t(s['sold_t'])} sold, {_t(s['recycled_t'])} recycled in plant. "
                         f"Recorded as diverted: {s['diversion_pct']}%.")
        out["answer"] = " ".join(lines)
    elif intent == "record_issue":
        parts = []
        for sid in sids:
            s = ctx["stream"](sid)
            if s["status"] == "OK":
                parts.append(f"{s['name']} records are consistent: only {s['readings'][1]['gap_pct']} to {s['readings'][0]['gap_pct']}% is unaccounted for.")
            else:
                parts.append(f"{s['name']} is flagged for review. Recorded recycled plus sold is {_t(s['recycled_t'] + s['sold_t'])} against "
                             f"{_t(s['generated_t'])} generated. If recycled tonnes are already inside the sold figure, "
                             f"{_t(s['gap_b'])} ({s['readings'][1]['gap_pct']}%) is still unaccounted for. Another cause can be sales from "
                             f"stock built in earlier years.")
        out["answer"] = " ".join(parts)
    elif intent == "unrecorded":
        parts = []
        for sid in sids:
            s = ctx["stream"](sid)
            if s["status"] == "OK":
                lo, hi = sorted([s["readings"][0]["gap_pct"], s["readings"][1]["gap_pct"]])
                tl, th = sorted([s["gap_a"], s["gap_b"]])
                parts.append(f"{s['name']}: {lo} to {hi}% of generated tonnes has no recorded use ({_t(tl)} to {_t(th)}).")
            else:
                parts.append(f"{s['name']}: the records are inconsistent. If recycled tonnes are already inside sold, {_t(s['gap_b'])} "
                             f"({s['readings'][1]['gap_pct']}%) has no recorded use. If they are separate, recorded uses exceed generation "
                             f"by {_t(s['excess_t'])}.")
        out["answer"] = " ".join(parts) + " The Form V extract does not report stockpile, so a stockpile share cannot be given."
    elif intent == "actions":
        acts = ctx["actions"]()[:4]
        out["answer"] = "Top recommended actions: " + " ".join(f"{i + 1}. {a['text']}" for i, a in enumerate(acts))
    elif intent == "scenario":
        p = parse_scenario(text)
        if not p:
            out["answer"] = ("Give me a percentage, for example 'What if we lose 30% of buyers?', 'What if slag output rises 10%?' "
                             "or 'What if we recover 10% more LD slag?'.")
        else:
            gen, buy, rec = p
            lines = []
            for sid in sids:
                r = ctx["scenario"](sid, gen, buy, rec)
                b, c = r["baseline"], r["scenario"]
                lines.append(f"{r['stream']}: diversion changes from {b['diversion_pct']}% to {c['diversion_pct']}%, and unmanaged slag from "
                             f"{_t(b['unmanaged_t'])} to {_t(c['unmanaged_t'])}.")
            out["answer"] = " ".join(lines) + " This is an assumption-based estimate, not a forecast."
    elif intent == "improve":
        worst = max(("bf", "bof"), key=lambda k: ctx["stream"](k)["readings"][1]["gap_pct"])
        s = ctx["stream"](worst)
        out["answer"] = (f"{s['name']} has the largest unaccounted share ({s['readings'][1]['gap_pct']}%, {_t(s['gap_b'])}). "
                         f"Closing it means finding a recorded use for those tonnes, for example by recovering them in-plant or by confirming sales. "
                         f"Also: confirm each buyer's end use, keep a second buyer qualified, and reconcile flagged records first. "
                         f"You can test the effect in the Scenario lab.")
    elif intent == "model_accuracy":
        out["answer"] = (f"On held-out data the energy model is off by {ctx['mae']:.1f} kWh on average per 15 minutes. The simple baseline "
                         f"('same as 15 minutes ago') is off by {ctx['persist_mae']:.1f} kWh. The model was trained on one plant's data for one year.")
    elif intent == "define":
        out["answer"] = ("Diversion rate = tonnes recorded as sold or recycled divided by tonnes generated. In-plant recovery = tonnes reused inside "
                         "the plant divided by tonnes generated. Unrecorded share = generated tonnes with no recorded use. "
                         "OBSERVED means read from a document, DERIVED means calculated from other facts, ASSUMED means an assumption.")
    elif intent == "sources":
        out["answer"] = ("Slag tonnes come from the Tata Steel Jamshedpur Form V for FY2021-22. The energy readings come from an open UCI steel-plant "
                         "dataset (2018) replayed in sequence. They are different plants, so the energy figures say nothing about the slag figures. "
                         "The values are replayed from datasets, not read live from a plant.")
    out["suggestions"] = SUGGEST.get(intent, SUGGEST[None])
    return out
