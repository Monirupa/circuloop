# CircuLoop

Advisory dashboard for in-plant circular economy in a steel plant. It shows where by-products (slag) go, checks the records against a knowledge graph, forecasts energy use with a plain-language explanation, lets staff test what-if changes, records their decisions, and answers questions in a chat panel.

The slag tonnes are the Tata Steel Jamshedpur Form V figures for FY2021-22. The energy readings are the open UCI steel-plant dataset (2018), replayed in sequence. They come from different plants. Nothing is connected to plant equipment, and the app only advises.

## Run it in VS Code or Antigravity (Windows)

1. Unzip the folder and open it (**File > Open Folder**, choose the `circuloop` folder that contains `app`, `data` and `train.py`).
2. Copy `Steel_industry_data.csv` into `data\raw\`.
3. Open a terminal and run:

```
powershell -ExecutionPolicy Bypass -File run.ps1
```

4. Open http://127.0.0.1:8000. If port 8000 is busy, add `-Port 8001` to the command and open that port instead.

`run.ps1` creates the virtual environment, installs the libraries, trains the model on the first run, builds the knowledge graph and starts the server. Stop it with Ctrl+C.

### Or step by step

```
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python train.py
python app\kg_build.py
uvicorn main:app --reload --app-dir app
```

## What is in the dashboard

| Page | What it shows |
|---|---|
| Overview | Plain-language insights, routing donuts for each slag stream, an energy gauge, the 24-hour chart, daily load profile, and the actions waiting for a decision. |
| Circular flow | An interactive map of the plant. Select any stage to see what happens, how it is circular and what to decide. Band widths show recorded tonnes. |
| Blast furnace, LD converter | Process text, where the slag is recorded to go, circularity figures, record check, actions with step-by-step guidance. |
| Plant energy | Forecast gauge, hover chart, typical daily load, model performance, SHAP explanation, actions. |
| Scenario lab | Sliders for output change, buyers lost and extra in-plant recovery, with side-by-side donuts and a flow diagram. All assumptions are labelled. |
| Decisions | Open actions and a time-stamped decision log (kept in the browser window only). |
| Records & sources | Data sources, the knowledge graph drawn as a diagram, and every fact with its source and basis. |

The status bar at the top is always visible. The **Ask CircuLoop** button opens the question assistant.

## The question assistant

`app/chat.py` matches each question to the closest example question using TF-IDF and cosine similarity (scikit-learn), picks out the stream and any percentage, and fills the answer from the live values. It uses no external service and cannot invent a number. It is not a generative model. To use a language model later, keep `classify()` and replace `answer()` with a call that is given the same values.

## What each file does

| File | Purpose |
|---|---|
| `app/prep.py` | Loads the energy CSV and builds the model inputs. |
| `train.py` | Trains the gradient boosting model, compares it with two baselines on a time-ordered test set, saves `models/energy_model.joblib`. |
| `app/narrate.py` | Turns SHAP contributions into a sentence. |
| `app/kg_build.py` | Builds the knowledge graph with source and basis on every fact, saves `data/kg.json`. |
| `app/content.py` | All dashboard wording: section text, step-by-step guidance, the flow map and its stage details. |
| `app/chat.py` | The question assistant. |
| `app/main.py` | FastAPI backend: record checks, indicators, scenarios, predictions, explanations, actions. |
| `app/static/index.html`, `style.css`, `app.js` | The dashboard. Colours are tokens at the top of `style.css`. |

## Extending it

- **More facts:** add `fact(...)` lines in `app/kg_build.py` (dust, scale, more plants). Fill in the `page` field from the PDF.
- **Live values later:** replace the replay with readings from your plant system by changing what `series` and `explain` in `app/main.py` read from.
- **Flow map:** edit `FLOW_NODES`, `FLOW_EDGES` and `FLOW_DETAIL` in `app/content.py`.
- **Thresholds:** `TOLERANCE_PCT` and `DEVIATION_X` in `app/main.py`.
- **Agents:** an agent that extracts facts from PDFs into the graph would replace the hand-entered `fact(...)` lines. Not built yet.

## Deploying (later)

Push the folder to GitHub (include `data/raw/Steel_industry_data.csv` and `models/energy_model.joblib` only if the dataset licence allows it), then create a Render web service from the repo. `render.yaml` holds the build and start commands.

## Limits to state in your report

- One plant's energy data for one year and one plant's annual slag filing. Nothing is validated at a live plant.
- The flow map shows quantities only where Form V gives them. Other routes describe typical practice.
- Recommendations and chat answers are rule-based. Scenario numbers are assumptions, not predictions.
