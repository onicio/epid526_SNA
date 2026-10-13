"""Interactive network in the browser with pyvis (pip install pyvis).
Creates vaccine_network.html: zoom, drag nodes, hover to see the account type."""
import networkx as nx
import pandas as pd
from pyvis.network import Network

BASE = "../../data/05_vaccine_conversation"
nodes = pd.read_csv(f"{BASE}/nodes.csv")
edges = pd.read_csv(f"{BASE}/edges.csv")
G = nx.from_pandas_edgelist(edges, "source", "target", edge_attr="weight", create_using=nx.DiGraph())
G.add_nodes_from(nodes.id)

colors = {"pro-vaccine": "#2a78d6", "anti-vaccine": "#eb6834", "hesitant": "#1baf7a", "neutral": "#b5b3ab"}
pr = nx.pagerank(G, weight="weight")
for row in nodes.itertuples():
    G.nodes[row.id].update(title=f"{row.id}: {row.account_type} ({row.stance})",
                           color=colors[row.stance], size=5 + 300 * pr[row.id])

net = Network(height="750px", width="100%", directed=True, cdn_resources="remote")
net.from_nx(G)
net.write_html("vaccine_network.html", open_browser=False, notebook=False)
print("open vaccine_network.html in your browser")
