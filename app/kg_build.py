import json
import os
import networkx as nx
from networkx.readwrite import json_graph

SRC = "Tata Steel Jamshedpur Form V FY2021-22"
G = nx.MultiDiGraph()

def node(i, typ, **kw): G.add_node(i, type=typ, **kw)
def edge(a, b, rel, **kw): G.add_edge(a, b, relation=rel, **kw)

node("Plant:JSR", "Plant", name="Tata Steel Jamshedpur")
node("Unit:BF", "ProcessUnit", name="Blast furnace")
node("Unit:BOF", "ProcessUnit", name="LD converter (BOF)")
node("Stream:BF_slag", "Stream", name="BF slag")
node("Stream:LD_slag", "Stream", name="LD (steel) slag")
node("Use:Recycled", "Use", name="Recycled in plant")
node("Use:Sold", "Use", name="Sold / dispatched")

edge("Plant:JSR", "Unit:BF", "HAS_UNIT")
edge("Plant:JSR", "Unit:BOF", "HAS_UNIT")

def fact(a, b, rel, t):
    edge(a, b, rel, quantity_t=t, source=SRC, page=None, basis="OBSERVED")

fact("Unit:BF", "Stream:BF_slag", "PRODUCES", 4351309)
fact("Stream:BF_slag", "Use:Recycled", "ROUTED_TO", 14018)
fact("Stream:BF_slag", "Use:Sold", "ROUTED_TO", 4305189)
fact("Unit:BOF", "Stream:LD_slag", "PRODUCES", 1614344)
fact("Stream:LD_slag", "Use:Recycled", "ROUTED_TO", 339308)
fact("Stream:LD_slag", "Use:Sold", "ROUTED_TO", 1533948)

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
with open("data/kg.json", "w") as f:
    json.dump(json_graph.node_link_data(G), f, indent=2)
print("knowledge graph saved to data/kg.json:", G.number_of_nodes(), "nodes,", G.number_of_edges(), "edges")
