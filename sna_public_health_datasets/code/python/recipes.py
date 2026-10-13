"""
Dataset-specific recipes (Python). Each block answers the guided questions of one dataset.
Run all:   python recipes.py            (from code/python, data in ../../data)
The blocks between "# %% [name]" and "# %% [end]" are copied into the guide.
"""
# %% [helper]
import numpy as np
import pandas as pd
import networkx as nx

BASE = "../../data"   # or "https://raw.githubusercontent.com/USER/REPO/main/data"


def load(dataset, directed):
    """Read nodes.csv and edges.csv and return (nodes, edges, graph). Isolates are kept."""
    nodes = pd.read_csv(f"{BASE}/{dataset}/nodes.csv")
    edges = pd.read_csv(f"{BASE}/{dataset}/edges.csv")
    G = nx.from_pandas_edgelist(edges, "source", "target", edge_attr=True,
                                create_using=nx.DiGraph() if directed else nx.Graph())
    for row in nodes.to_dict("records"):
        node_id = row.pop("id")
        G.add_node(node_id, **{k: v for k, v in row.items() if pd.notna(v)})
    return nodes, edges, G


def rank_table(measures):
    """measures: dict name -> {node: value}. Returns values and ranks side by side."""
    df = pd.DataFrame(measures)
    for m in measures:
        df[m + "_rank"] = df[m].rank(ascending=False, method="min").astype(int)
    return df
# %% [end]


def d1():
    # %% [d1]
    nodes, edges, G = load("01_school_vaping", directed=True)
    n = nodes.set_index("id")
    surveyed = n[n.completed_survey == 1]
    vape = surveyed.vaped_30d

    # (a) Mutual vs one-way friendships: do friends share vaping status?
    pairs = set(zip(edges.source, edges.target))
    edges["mutual"] = [(t, s) in pairs for s, t in zip(edges.source, edges.target)]
    e = edges[edges.source.isin(vape.index) & edges.target.isin(vape.index)].copy()
    e["both_vape"] = [vape[s] == 1 and vape[t] == 1 for s, t in zip(e.source, e.target)]
    e["source_vapes"] = [vape[s] == 1 for s in e.source]
    print("P(friend vapes | I vape), mutual vs one-way ties:")
    print(e[e.source_vapes].groupby("mutual").both_vape.mean().round(3))

    # (b) Degrees of separation (Christakis & Fowler style)
    U = G.to_undirected()
    vapers = list(vape[vape == 1].index)
    rows = []
    for alter in vapers:
        dist = nx.single_source_shortest_path_length(U, alter, cutoff=4)
        for ego, d in dist.items():
            if d > 0 and ego in vape.index:
                rows.append((d, vape[ego]))
    sep = pd.DataFrame(rows, columns=["distance", "ego_vapes"]).groupby("distance").ego_vapes.mean()
    print("\nP(ego vapes | a person at distance d vapes):")
    print(sep.round(3))
    print("baseline prevalence:", round(vape.mean(), 3))

    # (c) Choosing 46 peer leaders (10%): who reaches more students in one step?
    k = 46
    scores = {
        "in-degree": dict(G.in_degree()),
        "PageRank": nx.pagerank(G),
        "betweenness": nx.betweenness_centrality(G),
        "random": dict(zip(G.nodes(), np.random.default_rng(1).random(G.number_of_nodes()))),
    }
    for name, sc in scores.items():
        leaders = set(sorted(sc, key=sc.get, reverse=True)[:k])
        reached = set(leaders)
        for x in leaders:
            reached |= set(U.neighbors(x))
        print(f"{name:12s} leaders reach {len(reached) / G.number_of_nodes():.0%} of students")

    # (d) Perceived norm vs reality
    actual = [sum(vape.get(j, 0) == 1 for j in G.successors(i)) for i in surveyed.index]
    print("\nMean perceived number of vaping friends:", round(surveyed.perceived_friends_vaping.mean(), 2))
    print("Mean actual number among nominated friends:", round(np.mean(actual), 2))
    # %% [end]


def d2():
    # %% [d2]
    nodes, edges, G = load("02_nursing_home_flu", directed=False)
    n = nodes.set_index("id")
    for a, b, d in G.edges(data=True):
        d["distance"] = 1 / d["weight"]          # more minutes = "closer"

    # (a) Keep only "close contacts": 15 minutes or more in the week
    H = nx.Graph()
    H.add_nodes_from(G.nodes(data=True))
    H.add_edges_from((a, b, d) for a, b, d in G.edges(data=True) if d["weight"] >= 15)
    print("edges all / >=15 min:", G.number_of_edges(), "/", H.number_of_edges())

    # (b) Who connects the units? weighted betweenness
    btw = pd.Series(nx.betweenness_centrality(G, weight="distance"))
    top = btw.sort_values(ascending=False).head(8).index
    print(n.loc[top, ["role", "unit", "units_worked", "employment", "flu_vaccinated"]].assign(btw=btw[top].round(3)))

    # (c) Attack rates
    res = n[n.person_type == "resident"]
    print("\nResident attack rate by unit:")
    print(res.groupby("unit").flu_case.agg(["mean", "sum", "count"]).round(2))
    print("Attack rate by vaccination (everyone):")
    print(n.groupby("flu_vaccinated").flu_case.mean().round(3))
    n["degree"] = pd.Series(dict(G.degree()))
    n["degree_quartile"] = pd.qcut(n.degree, 4, labels=["Q1 (fewest)", "Q2", "Q3", "Q4 (most)"])
    print("Attack rate by degree quartile:")
    print(n.groupby("degree_quartile", observed=True).flu_case.mean().round(3))

    # (d) Epidemic curve: residents by unit, staff together
    cases = n[n.flu_case == 1].copy()
    cases["group"] = np.where(cases.person_type == "resident", "unit " + cases.unit, "staff")
    print("\nCases by week of onset:")
    print(pd.crosstab(cases.group, (cases.onset_day.astype(int) - 1) // 7 + 1).rename(columns=lambda w: f"week {w}"))

    # (e) Staff cohorting: what if nursing staff did not float between units?
    def residents_one_staff_away(graph):
        """Mean number of residents in OTHER units reachable through one staff member."""
        counts = []
        for r_id in res.index:
            others = set()
            for s_id in graph.neighbors(r_id):
                if n.loc[s_id, "person_type"] == "staff":
                    others |= {x for x in graph.neighbors(s_id)
                               if x in res.index and n.loc[x, "unit"] != n.loc[r_id, "unit"]}
            counts.append(len(others))
        return np.mean(counts)
    floaters = [i for i in n.index if n.loc[i, "role"] in ("CNA", "LPN", "RN") and "+" in str(n.loc[i, "units_worked"])]
    Hc = H.copy()
    Hc.remove_nodes_from(floaters)
    print(f"\nFloating nursing staff: {len(floaters)} people")
    print("Residents in other units only one staff member away (>=15 min contacts):",
          round(residents_one_staff_away(H), 1), "->", round(residents_one_staff_away(Hc), 1), "without floating staff")
    # %% [end]


def d3():
    # %% [d3]
    nodes, edges, G = load("03_older_adults_support", directed=True)
    n = nodes.set_index("id")
    res = n[n.node_type == "resident"].copy()

    # (a) Reciprocity by relationship and by mobility
    pairs = set(zip(edges.source, edges.target))
    edges["reciprocated"] = [(t, s) in pairs for s, t in zip(edges.source, edges.target)]
    print(edges.groupby("relationship").reciprocated.mean().round(2).sort_values())
    # node level: share of the people I count on who also count on me
    res["reciprocity"] = edges.groupby("source").reciprocated.mean()
    print(res.groupby("mobility_limitation").reciprocity.mean().round(2))

    # (b) Isolates: who are they?
    res["in_deg"] = pd.Series(dict(G.in_degree()))
    res["out_deg"] = pd.Series(dict(G.out_degree()))
    res["total_deg"] = res.in_deg + res.out_deg
    iso = res[res.total_deg == 0]
    print("\nIsolates:", len(iso))
    print(iso.neighborhood.value_counts())
    print("share living alone:", round(iso.lives_alone.mean(), 2), "| hearing loss:", round(iso.hearing_loss.mean(), 2))

    # (c) Ego-reported network (LSNS-6) vs sociocentric ties
    print("\nSpearman(LSNS-6, sociocentric degree):", round(res.lsns6.corr(res.total_deg, method="spearman"), 2))
    print(res.groupby(res.lsns6 < 12).total_deg.describe().round(1))

    # (d) Loneliness and number of ties
    res["ties_group"] = pd.cut(res.total_deg, [-1, 0, 2, 5, 100], labels=["0", "1-2", "3-5", "6+"])
    print(res.groupby("ties_group", observed=True).ucla3_loneliness.agg(["mean", "count"]).round(2))
    strain = edges.groupby("source").strain.sum()
    res["strain_total"] = strain.reindex(res.index).fillna(0)
    lonely_crowd = res[(res.ucla3_loneliness >= 6) & (res.total_deg >= 5)]
    print("lonely with 5+ ties:", len(lonely_crowd), "| mean strain:", round(lonely_crowd.strain_total.mean(), 2),
          "vs others:", round(res.strain_total.mean(), 2))

    # (e) Brokers, and what happens if the main community worker leaves
    btw = pd.Series(nx.betweenness_centrality(G)).sort_values(ascending=False)
    print(n.loc[btw.index[:6], ["role", "neighborhood", "language"]].assign(btw=btw[:6].round(3)))
    U = G.to_undirected()
    spanish = [i for i in res.index if res.loc[i, "language"] == "Spanish"]
    english = set(res.index[res.language == "English"])
    def steps_to_english(graph):
        d = []
        for s in spanish:
            if s in graph:
                dist = nx.single_source_shortest_path_length(graph, s)
                reach = [dist[e] for e in english if e in dist]
                if reach:
                    d.append(np.mean(reach))
        return round(np.mean(d), 2)
    U2 = U.copy()
    U2.remove_nodes_from(btw.index[:3])     # the three main brokers leave
    print("Mean steps from Spanish-speaking to English-speaking residents:",
          steps_to_english(U), "->", steps_to_english(U2), "without the top-3 brokers")
    # %% [end]


def d4():
    # %% [d4]
    nodes, edges, G = load("04_social_needs_referrals", directed=True)
    n = nodes.set_index("id")

    # (a) Three ways to be "important as a destination"
    t = rank_table({"in_degree": dict(G.in_degree()),
                    "in_strength": dict(G.in_degree(weight="weight")),
                    "pagerank": nx.pagerank(G, weight="weight")})
    t = t.join(n[["org_name", "org_type"]])
    print(t.sort_values("pagerank", ascending=False).head(8)[["org_name", "in_degree_rank", "in_strength_rank", "pagerank_rank"]])
    t["gain"] = t.in_degree_rank - t.pagerank_rank
    print("\nBiggest gain from in-degree rank to PageRank rank:")
    print(t.sort_values("gain", ascending=False).head(4)[["org_name", "in_degree_rank", "pagerank_rank"]])
    rent_src = edges[edges.target == t.sort_values("gain", ascending=False).index[0]]
    print("its referral sources:")
    print(rent_src.assign(src=n.loc[rent_src.source, "org_name"].values)[["src", "weight"]].sort_values("weight", ascending=False).head(5))

    # (b) Who sends and who receives? (out-degree vs in-degree by org type)
    flows = pd.DataFrame({"out": dict(G.out_degree()), "in": dict(G.in_degree())}).join(n.org_type)
    print(flows.groupby("org_type")[["out", "in"]].mean().round(1).sort_values("out", ascending=False).head(8))

    # (c) Reciprocity by sector pair
    pairs = set(zip(edges.source, edges.target))
    edges["reciprocated"] = [(b, a) in pairs for a, b in zip(edges.source, edges.target)]
    edges["pair"] = n.loc[edges.source, "sector"].values + " -> " + n.loc[edges.target, "sector"].values
    print(edges.groupby("pair").reciprocated.mean().round(2).sort_values())

    # (d) Cut vertices: organizations whose loss disconnects others
    U = G.to_undirected()
    cut = list(nx.articulation_points(U))
    print("\nArticulation points:", [(c, n.loc[c, "org_name"], n.loc[c, "region"]) for c in cut])
    biggest_cut = max(cut, key=lambda c: sorted(map(len, nx.connected_components(nx.restricted_view(U, [c], []))))[-2])
    U2 = U.copy()
    U2.remove_node(biggest_cut)
    print("Remove", n.loc[biggest_cut, "org_name"], "-> component sizes:",
          sorted(map(len, nx.connected_components(U2)), reverse=True)[:4])

    # (e) A client calls 211: how many referral steps to reach organizations in each region?
    helpline = n.index[n.org_type == "211 helpline"][0]
    steps = pd.Series(nx.single_source_shortest_path_length(G, helpline))
    receivers = [i for i in G if G.in_degree(i) > 0 and i != helpline]   # orgs that accept referrals
    reach = pd.DataFrame({"region": n.loc[receivers, "region"], "steps": steps.reindex(receivers)}).fillna({"steps": np.inf})
    print(reach.groupby("region").steps.agg(
        one_step=lambda s: (s == 1).mean(), two_steps_or_less=lambda s: (s <= 2).mean(),
        unreachable=lambda s: np.isinf(s).mean()).round(2))
    # %% [end]


def d5():
    # %% [d5]
    nodes, edges, G = load("05_vaccine_conversation", directed=True)
    n = nodes.set_index("id")

    # (a) In-degree vs PageRank: who rises, who falls?
    t = rank_table({"in_degree": dict(G.in_degree()), "pagerank": nx.pagerank(G, weight="weight")})
    t = t.join(n[["account_type", "stance", "followers"]])
    t["change"] = t.in_degree_rank - t.pagerank_rank
    cols = ["account_type", "stance", "in_degree", "in_degree_rank", "pagerank_rank"]
    print("Top 8 by PageRank (look at their in-degree rank):\n", t.sort_values("pagerank_rank").head(8)[cols])
    print("Top 8 by in-degree (look at their PageRank rank):\n", t.sort_values("in_degree_rank").head(8)[cols])

    # (b) Who reposts the accounts that fall? Look at the reposters' profile
    loser = t[t.in_degree_rank <= 15].sort_values("change").index[0]
    reposters = list(G.predecessors(loser))
    print("\nReposters of", loser, ":")
    print(n.loc[reposters].groupby("account_type")[["account_age_days", "posts_per_day", "automation_score"]].mean().round(1))

    # (c) Reciprocity by account type (reposting each other is unusual)
    pairs = set(zip(edges.source, edges.target))
    edges["reciprocated"] = [(b, a) in pairs for a, b in zip(edges.source, edges.target)]
    edges["type"] = n.loc[edges.source, "account_type"].values
    print(edges.groupby("type").reciprocated.agg(reciprocity="mean", ties="count").round(2)
          .sort_values("reciprocity", ascending=False).head(5))

    # (d) Eigenvector on the undirected network vs PageRank
    U = nx.Graph()
    for a, b, d in G.edges(data=True):
        w = U[a][b]["weight"] + d["weight"] if U.has_edge(a, b) else d["weight"]
        U.add_edge(a, b, weight=w)
    eig = pd.Series(nx.eigenvector_centrality(U, weight="weight", max_iter=2000))
    print("\nTop 10 eigenvector (undirected, weighted):", n.loc[eig.nlargest(10).index, "account_type"].value_counts().to_dict())
    pr = pd.Series(nx.pagerank(G, weight="weight"))
    print("Top 10 PageRank:", n.loc[pr.nlargest(10).index, "account_type"].value_counts().to_dict())

    # (e) Hubs and authorities (HITS)
    hubs, auth = nx.hits(G, max_iter=2000)
    print("Top 10 hubs:", n.loc[pd.Series(hubs).nlargest(10).index, "account_type"].value_counts().to_dict())

    # (f) Echo chambers and bridges
    comms = nx.community.louvain_communities(U, weight="weight", seed=42)
    memb = pd.Series({x: i for i, c in enumerate(comms) for x in c})
    print(pd.crosstab(memb, n.stance))
    btw = pd.Series(nx.betweenness_centrality(U)).nlargest(6)
    print(n.loc[btw.index, ["account_type", "stance", "language"]].assign(btw=btw.round(3)))
    # %% [end]


def d6():
    # %% [d6]
    nodes, edges, G = load("06_pwid_hiv_overdose", directed=False)
    n = nodes.set_index("id")

    # (a) One network, several layers
    def layer(col):
        L = nx.Graph()
        L.add_nodes_from(G.nodes())
        L.add_edges_from((a, b) for a, b, d in G.edges(data=True) if d[col] == 1)
        return L
    layers = {"all ties": G, "shared equipment": layer("shared_equipment"),
              "sex partners": layer("sex_partners"), "social support": layer("social_support")}
    for name, L in layers.items():
        b = pd.Series(nx.betweenness_centrality(L)).nlargest(3)
        print(f"{name:17s} edges={L.number_of_edges():4d} top betweenness:",
              [(i, n.loc[i, "role"][:4], n.loc[i, "location"]) for i in b.index])

    # (b) The dense core and HIV
    n["k_core"] = pd.Series(nx.core_number(G))
    print(pd.crosstab(n.k_core, n.hiv_status))

    # (c) Remove the top bridge of the risk layer
    risk = layers["shared equipment"]
    bridge = pd.Series(nx.betweenness_centrality(risk)).idxmax()
    before = sorted(map(len, nx.connected_components(risk)), reverse=True)[:3]
    risk2 = risk.copy()
    risk2.remove_node(bridge)
    after = sorted(map(len, nx.connected_components(risk2)), reverse=True)[:3]
    print("\nRisk layer components before / after removing", bridge, ":", before, "/", after)

    # (d) Naloxone coverage: does each person who injects have a naloxone carrier among their ties?
    carriers = set(n.index[n.carries_naloxone == 1])
    pwid = n[n.role == "PWID"].copy()
    pwid["covered"] = [any(j in carriers for j in G.neighbors(i)) for i in pwid.index]
    print(pwid.groupby("location").covered.mean().round(2))

    # (e) Train 10 more people: pick by degree or by greedy coverage?
    uncovered = set(pwid.index[~pwid.covered])
    cands = [i for i in pwid.index if i not in carriers]
    by_degree = sorted(cands, key=G.degree, reverse=True)[:10]
    greedy, left = [], set(uncovered)
    for _ in range(10):
        best = max(cands, key=lambda c: len(left & (set(G.neighbors(c)) | {c})))
        greedy.append(best)
        left -= set(G.neighbors(best)) | {best}
    def newly_covered(chosen):
        cov = set()
        for c in chosen:
            cov |= (set(G.neighbors(c)) | {c}) & uncovered
        return len(cov)
    print(f"uncovered PWID: {len(uncovered)} | covered by top-degree picks: {newly_covered(by_degree)} "
          f"| by greedy picks: {newly_covered(greedy)}")
    # %% [end]


if __name__ == "__main__":
    for f in (d1, d2, d3, d4, d5, d6):
        print("\n" + "=" * 70 + f"\n{f.__name__}\n" + "=" * 70)
        f()
