# Social Network Analysis in Public Health: Teaching Datasets

Six synthetic network datasets about public health problems, with a guide in Markdown and ready-to-run code in Python and R. Made for a first experience with social network analysis (SNA).

> All people and organizations are simulated. Do not use the numbers to make conclusions about the real world.

**Start here: [docs/SNA_Public_Health_Guide.md](docs/SNA_Public_Health_Guide.md)**

| # | Dataset | Nodes | Ties | Public health challenge | Measures to explore |
|---|---|---|---|---|---|
| 1 | [`01_school_vaping`](data/01_school_vaping) | 460 students | friendship nominations (directed) | youth vaping | reciprocity, in-degree vs PageRank, bridges, isolates |
| 2 | [`02_nursing_home_flu`](data/02_nursing_home_flu) | 390 residents and staff | minutes of close contact | influenza outbreak | weighted betweenness, closeness, eigenvector, cohorting |
| 3 | [`03_older_adults_support`](data/03_older_adults_support) | 360 older adults and community workers | who counts on whom (directed) | loneliness and isolation | reciprocity, isolates, brokers, PageRank |
| 4 | [`04_social_needs_referrals`](data/04_social_needs_referrals) | 320 organizations | referrals (directed, weighted) | food, housing and care access | PageRank, betweenness, cut vertex |
| 5 | [`05_vaccine_conversation`](data/05_vaccine_conversation) | 500 accounts | reposts (directed, weighted) | vaccine hesitancy and misinformation | echo chambers, bots, PageRank vs eigenvector |
| 6 | [`06_pwid_hiv_overdose`](data/06_pwid_hiv_overdose) | 380 people | injection, sex, support, overdose response | HIV, hepatitis C, overdose | k-core, network layers, bridges, naloxone coverage |

Each folder has `nodes.csv`, `edges.csv` and `network.graphml` (for Gephi or Cytoscape).

## Quick start

**Python (Google Colab or Jupyter)**: open [`code/python/sna_walkthrough.ipynb`](code/python/sna_walkthrough.ipynb), change `DATASET` and run all cells.

```bash
pip install pandas networkx matplotlib scipy
cd code/python
python sna_walkthrough.py 03_older_adults_support
```

**R (RStudio)**: open [`code/R/sna_walkthrough.R`](code/R/sna_walkthrough.R), change `dataset` and run.

```r
install.packages(c("igraph", "tidygraph", "ggraph", "readr", "dplyr", "ggplot2"))
```

```bash
cd code/R
Rscript sna_walkthrough.R 03_older_adults_support
```

Both walkthroughs compute the same measures (degree, strength, betweenness, closeness, harmonic closeness, eigenvector, PageRank, reciprocity, k-cores, Louvain communities, assortativity) and save a figure and a results table in `outputs/`. Dataset-specific exercises are in `recipes.py` and `recipes.R`.

## Repository structure

```text
data/        six datasets (nodes.csv, edges.csv, network.graphml)
code/python  walkthrough (script and notebook), recipes, interactive plot
code/R       walkthrough, recipes, interactive plot, ERGM example (statnet)
docs/        the guide and its figures
```

New to GitHub? See the [GitHub quick wizard](docs/SNA_Public_Health_Guide.md#7-github-quick-wizard) in the guide.

## Conceptual model

The datasets follow the conceptual model of Berkman and Krishna (2014), *Social network epidemiology*, chapter 7 of *Social Epidemiology* (2nd ed., Oxford University Press): social-structural conditions shape social networks, networks give opportunities for psychosocial mechanisms (support, influence, engagement, person-to-person contact, access to resources, negative interactions), and these mechanisms affect health through behavioral, psychological and physiological pathways.
