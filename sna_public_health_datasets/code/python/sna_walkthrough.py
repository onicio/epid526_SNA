"""
Social network analysis walkthrough (Python)
============================================
Works with any of the six datasets in ../../data

Run from the terminal:
    python sna_walkthrough.py 01_school_vaping
or open the notebook version (sna_walkthrough.ipynb) in Jupyter / Google Colab.

Packages: pandas, networkx (>= 3.0), matplotlib, scipy
    pip install pandas networkx matplotlib scipy
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")            # draw to files (remove this line in Jupyter)
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

# ---------------------------------------------------------------------------
# STEP 0. Choose the dataset
# ---------------------------------------------------------------------------
DATASET = sys.argv[1] if len(sys.argv) > 1 else "01_school_vaping"

# Read from the local copy of the repository ...
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / DATASET
# ... or directly from GitHub (replace USER/REPO with the course repository):
# DATA_DIR = "https://raw.githubusercontent.com/USER/REPO/main/data/" + DATASET

# Basic facts about each dataset (directed or not, and one attribute to color by)
CONFIG = {
    "01_school_vaping":          {"directed": True,  "color_by": "vaped_30d"},
    "02_nursing_home_flu":       {"directed": False, "color_by": "flu_case"},
    "03_older_adults_support":   {"directed": True,  "color_by": "language"},
    "04_social_needs_referrals": {"directed": True,  "color_by": "sector"},
    "05_vaccine_conversation":   {"directed": True,  "color_by": "stance"},
    "06_pwid_hiv_overdose":      {"directed": False, "color_by": "hiv_status"},
}
directed = CONFIG[DATASET]["directed"]
color_by = CONFIG[DATASET]["color_by"]
OUT = Path("outputs") / DATASET
OUT.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# STEP 1. Load the two tables: nodes (one row per person/organization)
#         and edges (one row per tie)
# ---------------------------------------------------------------------------
nodes = pd.read_csv(f"{DATA_DIR}/nodes.csv")
edges = pd.read_csv(f"{DATA_DIR}/edges.csv")
print(f"\n=== {DATASET} ===")
print("nodes table:", nodes.shape, "| edges table:", edges.shape)
print(nodes.head(3).T)
print(edges.head(3))
print("\nMissing values per column (nodes):")
print(nodes.isna().sum()[nodes.isna().sum() > 0])

# ---------------------------------------------------------------------------
# STEP 2. Build the graph
#   - edges first (with all edge attributes)
#   - then add ALL nodes with their attributes: this keeps the isolates
#     (people with no ties), who are invisible in the edge list
# ---------------------------------------------------------------------------
G = nx.from_pandas_edgelist(
    edges, source="source", target="target", edge_attr=True,
    create_using=nx.DiGraph() if directed else nx.Graph(),
)
for row in nodes.to_dict("records"):
    node_id = row.pop("id")
    # keep only non-missing attributes (a missing value becomes "no attribute")
    G.add_node(node_id, **{k: v for k, v in row.items() if pd.notna(v)})

# Our weights mean "stronger tie" (more minutes, more referrals...).
# Path-based measures (betweenness, closeness) need a DISTANCE, so we invert.
for u, v, d in G.edges(data=True):
    d["distance"] = 1 / d["weight"]

# An undirected copy is useful for some measures (communities, clustering, eigenvector).
# When A->B and B->A both exist they become one edge, and we SUM the two weights.
def to_undirected_sum(G):
    U = nx.Graph()
    U.add_nodes_from(G.nodes(data=True))
    for a, b, d in G.edges(data=True):
        if U.has_edge(a, b):
            U[a][b]["weight"] += d["weight"]
        else:
            U.add_edge(a, b, weight=d["weight"])
    for a, b, d in U.edges(data=True):
        d["distance"] = 1 / d["weight"]
    return U


U = to_undirected_sum(G) if directed else G

# ---------------------------------------------------------------------------
# STEP 3. Describe the whole network
# ---------------------------------------------------------------------------
print("\n--- Network description ---")
print("Nodes:", G.number_of_nodes(), " Edges:", G.number_of_edges())
print("Density:", round(nx.density(G), 4))
print("Isolates:", nx.number_of_isolates(G))
comps = sorted(nx.connected_components(U), key=len, reverse=True)
print("Connected components:", len(comps), "| largest:", len(comps[0]))
print("Transitivity (global clustering):", round(nx.transitivity(U), 3))
print("Average clustering (local):", round(nx.average_clustering(U), 3))
if directed:
    print("Reciprocity:", round(nx.reciprocity(G), 3))
    print("Strongly connected components:", nx.number_strongly_connected_components(G))
largest = U.subgraph(comps[0])
print("Average shortest path (largest component):", round(nx.average_shortest_path_length(largest), 2))

# Degree distribution
deg_series = pd.Series(dict(G.in_degree() if directed else G.degree()))
fig, ax = plt.subplots(figsize=(6, 3.5))
ax.hist(deg_series, bins=range(0, int(deg_series.max()) + 2), color="#2a78d6", edgecolor="#fcfcfb")
ax.set_xlabel("in-degree" if directed else "degree")
ax.set_ylabel("number of nodes")
ax.set_title("Degree distribution")
fig.tight_layout()
fig.savefig(OUT / "degree_distribution.png", dpi=150)
plt.close(fig)

# ---------------------------------------------------------------------------
# STEP 4. Centrality: who is important, and important for what?
# ---------------------------------------------------------------------------
cent = pd.DataFrame(index=list(G.nodes()))
if directed:
    cent["in_degree"] = pd.Series(dict(G.in_degree()))
    cent["out_degree"] = pd.Series(dict(G.out_degree()))
    cent["in_strength"] = pd.Series(dict(G.in_degree(weight="weight")))
else:
    cent["degree"] = pd.Series(dict(G.degree()))
    cent["strength"] = pd.Series(dict(G.degree(weight="weight")))

# Betweenness: how often a node sits on shortest paths between others (bridges, brokers)
cent["betweenness"] = pd.Series(nx.betweenness_centrality(G, normalized=True))
cent["betweenness_w"] = pd.Series(nx.betweenness_centrality(G, weight="distance", normalized=True))

# Closeness: how near a node is to all others. With isolates or many components,
# harmonic centrality is safer (unreachable nodes add 0 instead of breaking the measure).
cent["closeness"] = pd.Series(nx.closeness_centrality(U))
cent["harmonic"] = pd.Series(nx.harmonic_centrality(U))

# Eigenvector: being tied to well-connected nodes. For directed networks we use the
# undirected version (directed eigenvector gives 0 to everyone nobody points to).
cent["eigenvector"] = pd.Series(nx.eigenvector_centrality(U, max_iter=2000, weight="weight"))

# PageRank: like eigenvector but for directed ties, with "random jumps" (damping 0.85)
cent["pagerank"] = pd.Series(nx.pagerank(G, alpha=0.85, weight="weight"))

cent = nodes.set_index("id").join(cent)
cent.to_csv(OUT / "centrality_table.csv")

measures = [c for c in ["in_degree", "degree", "strength", "in_strength", "betweenness",
                        "closeness", "harmonic", "eigenvector", "pagerank"] if c in cent]
for m in measures:
    print(f"\nTop 5 by {m}:")
    print(cent.sort_values(m, ascending=False).head(5)[[m]].round(4))

# Do the measures agree? Spearman rank correlation
print("\nSpearman correlation between measures:")
print(cent[measures].corr(method="spearman").round(2))

# ---------------------------------------------------------------------------
# STEP 5. Reciprocity (directed networks only)
# ---------------------------------------------------------------------------
if directed:
    pairs = set(zip(edges["source"], edges["target"]))
    edges["reciprocated"] = [(t, s) in pairs for s, t in zip(edges["source"], edges["target"])]
    print("\nShare of ties that are reciprocated:", round(edges["reciprocated"].mean(), 3))
    # node level: share of the ties a node SENDS that come back
    node_recip = edges.groupby("source")["reciprocated"].mean()
    cent["reciprocity"] = node_recip
    print("Node-level reciprocity, summary:")
    print(node_recip.describe().round(2))

# ---------------------------------------------------------------------------
# STEP 6. Clusters: components, k-cores and communities
# ---------------------------------------------------------------------------
core = nx.core_number(nx.Graph(U))        # k-core: dense "inner" groups
cent["k_core"] = pd.Series(core)
print("\nLargest k-core:", max(core.values()), "with", sum(v == max(core.values()) for v in core.values()), "nodes")

communities = nx.community.louvain_communities(U, weight="weight", seed=42)
membership = {n: i for i, c in enumerate(communities) for n in c}
cent["community"] = pd.Series(membership)
Q = nx.community.modularity(U, communities, weight="weight")
print("Louvain communities:", len(communities), "| modularity Q =", round(Q, 3))
print("Do communities match the attribute?")
print(pd.crosstab(cent["community"], cent[color_by].fillna("missing")).head(12))

# ---------------------------------------------------------------------------
# STEP 7. Homophily: are ties more common between similar nodes?
# ---------------------------------------------------------------------------
has_attr = [n for n, d in G.nodes(data=True) if color_by in d]   # skip missing values
r = nx.attribute_assortativity_coefficient(G.subgraph(has_attr), color_by)
print(f"\nAssortativity by {color_by}: {r:.3f}  (0 = random mixing, 1 = only within group)")

# E-I index: (external - internal ties) / all ties, -1 = all ties inside groups
grp = nx.get_node_attributes(G, color_by)
internal = sum(1 for u, v in G.edges() if u in grp and v in grp and grp[u] == grp[v])
external = sum(1 for u, v in G.edges() if u in grp and v in grp and grp[u] != grp[v])
print("E-I index:", round((external - internal) / (external + internal), 3))

# ---------------------------------------------------------------------------
# STEP 8. Draw the network
# ---------------------------------------------------------------------------
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a"]   # blue, orange, aqua; gray = other / missing


def as_label(x):
    if pd.isna(x):
        return "missing"
    if isinstance(x, float) and x.is_integer():
        return str(int(x))          # 1.0 -> "1"
    return str(x)


def layout_with_isolates(U, seed=7):
    """Layout for the largest component; small components and isolates in a row below."""
    giant = max(nx.connected_components(U), key=len)
    H = U.subgraph(giant)
    try:
        pos = nx.forceatlas2_layout(H, seed=seed, max_iter=300, scaling_ratio=2.0)  # networkx >= 3.4
    except AttributeError:
        pos = nx.spring_layout(H, seed=seed, iterations=200)
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    pos = {n: (2 * (x - min(xs)) / (max(xs) - min(xs)) - 1, 2 * (y - min(ys)) / (max(ys) - min(ys)) - 1)
           for n, (x, y) in pos.items()}
    rest = sorted(n for n in U if n not in giant)
    for i, n in enumerate(rest):
        pos[n] = (-1 + 2 * (i + 0.5) / len(rest), -1.15)
    return pos


values = cent[color_by].map(as_label)
cats = [c for c in values.value_counts().index if c != "missing"][:3]
color_map = {c: PALETTE[i] for i, c in enumerate(cats)}
node_colors = [color_map.get(values[n], "#b5b3ab") for n in G.nodes()]
size_measure = "pagerank" if directed else "degree"
s = cent.loc[list(G.nodes()), size_measure]
node_sizes = 15 + 400 * (s - s.min()) / (s.max() - s.min())

pos = layout_with_isolates(U)
fig, ax = plt.subplots(figsize=(9, 9))
ax.set_facecolor("#fcfcfb")
nx.draw_networkx_edges(U, pos, ax=ax, edge_color="#c3c2b7", alpha=0.35, width=0.5)
nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors, node_size=node_sizes,
                       edgecolors="#fcfcfb", linewidths=0.6)
top_nodes = cent.sort_values("betweenness", ascending=False).head(5).index
nx.draw_networkx_labels(G, pos, labels={n: n for n in top_nodes}, font_size=8, ax=ax)
for c, col in color_map.items():
    ax.scatter([], [], color=col, label=c)
ax.scatter([], [], color="#b5b3ab", label="other / missing")
ax.legend(title=color_by, loc="lower left", frameon=False)
ax.set_title(f"{DATASET}: color = {color_by}, size = {size_measure}, labels = top-5 betweenness")
ax.axis("off")
fig.tight_layout()
fig.savefig(OUT / "network.png", dpi=150)
plt.close(fig)

# ---------------------------------------------------------------------------
# STEP 9. Save results (CSV for Excel/R, GraphML for Gephi or Cytoscape)
# ---------------------------------------------------------------------------
cent.to_csv(OUT / "node_results.csv")
G_export = G.copy()
for n, d in G_export.nodes(data=True):
    for k in list(d):
        if pd.isna(d[k]):
            del d[k]          # GraphML cannot store missing values
    d["community"] = int(membership[n])
    d["pagerank"] = float(cent.loc[n, "pagerank"])
    d["betweenness"] = float(cent.loc[n, "betweenness"])
nx.write_graphml(G_export, OUT / "network_with_results.graphml")
print(f"\nSaved figures and tables in {OUT}/")
