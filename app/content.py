"""Plain-text content for the dashboard: section descriptions, step-by-step guidance and the
factory flow map. Edit the wording here without touching the logic in main.py.

Facts that carry a number come from the knowledge graph (Form V). Everything else on the flow map
describes typical steelmaking practice and is labelled as such in the interface.
"""

SECTIONS = {
    "bf": {
        "name": "Blast furnace", "stream": "Stream:BF_slag",
        "process": ("Iron ore, coke and limestone are charged into the blast furnace. Hot blast reduces the ore "
                    "to molten iron (hot metal). The non-metallic part melts into blast furnace (BF) slag, which is "
                    "tapped alongside the hot metal. Typical BF slag generation is about 300-540 kg per tonne of pig "
                    "iron (Indian Minerals Yearbook 2018)."),
        "how_circular": ("Granulated BF slag replaces part of the clinker in slag cement, so most of it leaves the plant "
                         "as a product, not waste. A small part is reused inside the plant. The circular question is how "
                         "much of it is sold for a verified use."),
        "circular_note": "Stockpile share is not reported in the Form V extract.",
    },
    "bof": {
        "name": "LD converter", "stream": "Stream:LD_slag",
        "process": ("Hot metal and scrap are charged into the LD converter and oxygen is blown in to make steel. Lime and "
                    "dolomite form LD (steel) slag, about 150-200 kg per tonne of liquid steel (Indian Minerals Yearbook "
                    "2018)."),
        "how_circular": ("Metallic iron is recovered from the slag and returned to the furnace. The rest is used as road base, "
                         "ballast or fill, but free lime means it often needs treatment or ageing first, so unprocessed slag "
                         "builds up as stockpile across the industry."),
        "circular_note": "Stockpile share is not reported in the Form V extract.",
    },
}

# Concrete steps shown under each recommended action. Generic good practice, not plant-specific orders.
STEPS = {
    "reconcile": ["Pull the weighbridge and dispatch register for the filing year.",
                  "Separate in-plant movements (recycled) from external sales.",
                  "Compare the sum of both with the tonnes recorded as generated.",
                  "Correct the Form V entries once the difference is explained."],
    "double": ["Ask the records team whether recycled tonnes were also entered as sales.",
               "If they were, remove the duplicate and recompute the indicators.",
               "Note the corrected figure in the knowledge graph with its source."],
    "stock": ["Find the opening and closing stockpile for the year.",
              "Check whether any sales were made from stock built in earlier years.",
              "Record the stockpile change as its own line, so it is not hidden in sales."],
    "provisional": ["Mark the indicators as provisional in any report.",
                    "Re-check them after the records are reconciled."],
    "gap": ["List the dispatches and uses that have been recorded.",
            "Walk the yard to see whether the missing tonnes are in a stockpile.",
            "Record the end use or the stockpile for the missing tonnes."],
    "monitor": ["Repeat the check each time new records are entered."],
    "verify": ["Ask each buyer for a short end-use confirmation.",
               "Record the confirmation against the sale in the knowledge graph.",
               "Report 'verified use' separately from 'sold'."],
    "dev": ["Check the furnace and mill logs for an unplanned start or stop.",
            "Check the meter reading against the sub-meter or the previous reading.",
            "If both are normal, note the reading as an unexplained deviation."],
    "high": ["Confirm which heats are planned in the next hour.",
             "Tell the shift supervisor that a high-load period is expected."],
    "ok": ["No steps needed."],
}

# ---------------------------------------------------------------- factory flow map
# Coordinates are for an SVG of 1000 x 540. Node boxes are 156 x 56, centred on (x, y).
FLOW_NODES = [
    {"id": "raw",    "label": "Raw materials",        "x": 90,  "y": 90,  "type": "process"},
    {"id": "bf",     "label": "Blast furnace",        "x": 300, "y": 90,  "type": "process"},
    {"id": "bof",    "label": "LD converter",         "x": 510, "y": 90,  "type": "process"},
    {"id": "cast",   "label": "Casting & rolling",    "x": 720, "y": 90,  "type": "process"},
    {"id": "steel",  "label": "Steel products",       "x": 915, "y": 90,  "type": "market"},
    {"id": "sinter", "label": "Sinter plant",         "x": 90,  "y": 250, "type": "loop"},
    {"id": "bfslag", "label": "BF slag",              "x": 300, "y": 250, "type": "byproduct"},
    {"id": "ldslag", "label": "LD slag",              "x": 510, "y": 250, "type": "byproduct"},
    {"id": "dust",   "label": "Dust, sludge & scale", "x": 720, "y": 250, "type": "byproduct"},
    {"id": "cement", "label": "Cement & road buyers", "x": 190, "y": 420, "type": "market"},
    {"id": "recov",  "label": "Metal recovery",       "x": 410, "y": 420, "type": "loop"},
    {"id": "roads",  "label": "Road & ballast buyers", "x": 620, "y": 420, "type": "market"},
]

# kind: main = product line, by = by-product leaving a process, loop = material returning to the process
FLOW_EDGES = [
    {"id": "e1", "from": "raw", "to": "bf", "kind": "main", "d": "M168,90 H222", "label": "", "lx": 195, "ly": 78},
    {"id": "e2", "from": "bf", "to": "bof", "kind": "main", "d": "M378,90 H432", "label": "hot metal", "lx": 405, "ly": 50},
    {"id": "e3", "from": "bof", "to": "cast", "kind": "main", "d": "M588,90 H642", "label": "steel", "lx": 615, "ly": 50},
    {"id": "e4", "from": "cast", "to": "steel", "kind": "main", "d": "M798,90 H837", "label": "", "lx": 818, "ly": 78},
    {"id": "e5", "from": "bf", "to": "bfslag", "kind": "by", "d": "M300,118 V222", "label": "", "lx": 300, "ly": 170},
    {"id": "e6", "from": "bof", "to": "ldslag", "kind": "by", "d": "M510,118 V222", "label": "", "lx": 510, "ly": 170},
    {"id": "e7", "from": "cast", "to": "dust", "kind": "by", "d": "M720,118 V222", "label": "", "lx": 720, "ly": 170},
    {"id": "e8", "from": "bfslag", "to": "cement", "kind": "by", "d": "M270,278 L214,392", "label": "sold", "lx": 214, "ly": 330, "stream": "bf", "use": "sold"},
    {"id": "e9", "from": "ldslag", "to": "recov", "kind": "by", "d": "M474,278 L440,392", "label": "recycled", "lx": 449, "ly": 332, "anchor": "start", "stream": "bof", "use": "rec"},
    {"id": "e10", "from": "ldslag", "to": "roads", "kind": "by", "d": "M548,278 L598,392", "label": "sold", "lx": 644, "ly": 332, "stream": "bof", "use": "sold"},
    {"id": "e11", "from": "recov", "to": "bof", "kind": "loop", "d": "M382,392 V190 Q382,112 432,106", "label": "metal returns", "lx": 392, "ly": 205, "anchor": "start"},
    {"id": "e12", "from": "dust", "to": "sinter", "kind": "loop", "d": "M720,278 V508 H90 V278", "label": "dust, sludge and scale recycled", "lx": 405, "ly": 496},
    {"id": "e13", "from": "sinter", "to": "raw", "kind": "loop", "d": "M90,222 V118", "label": "", "lx": 90, "ly": 170},
]

FLOW_DETAIL = {
    "raw": {
        "what": "Iron ore, coking coal, limestone and dolomite are brought in and prepared for the blast furnace.",
        "circular": "Every tonne of recycled material (scrap, sinter fines, recovered dust) replaces virgin ore or coke.",
        "decide": ["Ask what recycled inputs the plant can accept before buying more virgin material.",
                   "Track recycled inputs as a share of the charge: it is the recycled-input indicator."],
    },
    "bf": {
        "what": "Ore is reduced to molten iron. BF slag leaves with the iron and is separated at the cast house.",
        "circular": "BF gas is cleaned and normally used as fuel in the plant. BF slag is granulated for cement.",
        "decide": ["Keep granulation capacity matched to slag output, so slag is not dumped.",
                   "Keep more than one slag buyer, so one buyer leaving does not create a stockpile."],
    },
    "bof": {
        "what": "Hot metal and scrap are refined to steel with oxygen. LD slag forms on top of the steel.",
        "circular": "Metal recovered from LD slag goes back into the converter charge.",
        "decide": ["Compare recovered metal against slag generated: a low ratio means metal is being lost.",
                   "Schedule slag pot handling so slag can be treated before it is sold."],
    },
    "cast": {
        "what": "Steel is cast and rolled. Mill scale, sludge and off-cuts are produced here.",
        "circular": "Off-cuts return to steelmaking as scrap. Scale and sludge can go to the sinter plant.",
        "decide": ["Send clean scale and cut-ends back to the plant instead of selling them cheaply.",
                   "Log scale and sludge tonnes. They are rarely tracked, so their fate is often unknown."],
    },
    "steel": {
        "what": "Finished steel leaves the plant boundary.",
        "circular": "Steel itself is highly recyclable: scrap from its end of life feeds the next furnace.",
        "decide": ["Nothing to decide inside the plant. This marks the boundary of the model."],
    },
    "sinter": {
        "what": "Fine ore, dust and scale are agglomerated into sinter that is charged to the blast furnace.",
        "circular": "The sinter plant is a main route for returning in-plant fines, dust and scale.",
        "decide": ["Check the zinc and alkali content of dust before recycling it: some dusts limit what the furnace can accept.",
                   "Record tonnes of dust and scale returned to sinter. This is the in-plant recovery indicator."],
    },
    "bfslag": {
        "what": "BF slag is generated at about 300-540 kg per tonne of pig iron and is usually granulated by water quenching.",
        "circular": "Most of it is sold to slag-cement and road-base users. Ask whether each sale has a confirmed end use.",
        "decide": ["If buyers fall away, unmanaged slag grows quickly. Test this in the Scenario lab.",
                   "Report 'verified use' separately from 'sold'."],
    },
    "ldslag": {
        "what": "LD slag is generated at about 150-200 kg per tonne of liquid steel and contains free lime and some metal.",
        "circular": "Recover the metal, then treat or age the slag before using it as road base or ballast.",
        "decide": ["Do not sell untreated slag for uses that need volume stability.",
                   "Keep treatment, stockpile and sales as separate records, so the totals can be checked."],
    },
    "dust": {
        "what": "Dust, sludge and mill scale are collected from gas cleaning and rolling.",
        "circular": "These are rich in iron and can return to the sinter plant, once zinc content is checked.",
        "decide": ["Test composition before recycling. Zinc can limit how much a furnace can take.",
                   "Count the tonnes: unknown fate here is the hardest share to see."],
    },
    "cement": {
        "what": "Cement makers and road-base users buy granulated BF slag.",
        "circular": "This is the main circular route for BF slag.",
        "decide": ["Ask for end-use confirmation and keep the record.",
                   "Keep a second buyer qualified in case the first stops."],
    },
    "recov": {
        "what": "Magnetic separation and crushing recover metallic iron from steel slag, and the remainder is made ready for use.",
        "circular": "Recovered metal returns to the converter, so it is the shortest loop in the plant.",
        "decide": ["Compare tonnes recovered with slag generated to see whether the loop is working.",
                   "Increase recovery here and watch the in-plant recovery indicator move (Scenario lab)."],
    },
    "roads": {
        "what": "Road builders and fill contractors buy treated LD slag as aggregate.",
        "circular": "Treated steel slag replaces natural aggregate.",
        "decide": ["Confirm that the slag was treated or aged before dispatch.",
                   "Record the project or buyer, so the use can be verified."],
    },
}
