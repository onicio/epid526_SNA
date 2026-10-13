# =============================================================================
# Social network analysis walkthrough (R)
# Works with any of the six datasets in ../../data
#
# Run in RStudio (open the project folder first) or in the terminal:
#   Rscript sna_walkthrough.R 01_school_vaping
#
# Packages (install once):
#   install.packages(c("igraph", "tidygraph", "ggraph", "readr", "dplyr", "ggplot2"))
# =============================================================================
suppressPackageStartupMessages({
  library(igraph)     # network objects and measures
  library(readr)      # read_csv()
  library(dplyr)      # data wrangling
  library(ggplot2)    # plots
  library(tidygraph)  # tidy interface to igraph
  library(ggraph)     # network plots with ggplot2 grammar
})

# -----------------------------------------------------------------------------
# STEP 0. Choose the dataset
# -----------------------------------------------------------------------------
args <- commandArgs(trailingOnly = TRUE)
dataset <- if (length(args) > 0) args[1] else "01_school_vaping"

# Local copy of the repository (working directory = code/R) ...
data_dir <- file.path("..", "..", "data", dataset)
# ... or directly from GitHub (works when the repository is public):
# data_dir <- paste0("https://raw.githubusercontent.com/onicio/epid526_SNA/main/data/", dataset)

config <- list(
  "01_school_vaping"          = list(directed = TRUE,  color_by = "vaped_30d"),
  "02_nursing_home_flu"       = list(directed = FALSE, color_by = "flu_case"),
  "03_older_adults_support"   = list(directed = TRUE,  color_by = "language"),
  "04_social_needs_referrals" = list(directed = TRUE,  color_by = "sector"),
  "05_vaccine_conversation"   = list(directed = TRUE,  color_by = "stance"),
  "06_pwid_hiv_overdose"      = list(directed = FALSE, color_by = "hiv_status")
)
directed <- config[[dataset]]$directed
color_by <- config[[dataset]]$color_by
out_dir <- file.path("outputs", dataset)
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

# -----------------------------------------------------------------------------
# STEP 1. Load the two tables
# -----------------------------------------------------------------------------
nodes <- read_csv(file.path(data_dir, "nodes.csv"), show_col_types = FALSE)
edges <- read_csv(file.path(data_dir, "edges.csv"), show_col_types = FALSE)
cat("\n===", dataset, "===\n")
cat("nodes:", nrow(nodes), "rows |", "edges:", nrow(edges), "rows\n")
print(head(nodes, 3))
print(head(edges, 3))
cat("\nMissing values per column (nodes):\n")
na_count <- colSums(is.na(nodes))
print(na_count[na_count > 0])

# -----------------------------------------------------------------------------
# STEP 2. Build the graph
#   vertices = nodes keeps the isolates (people with no ties)
# -----------------------------------------------------------------------------
g <- graph_from_data_frame(d = edges, vertices = nodes, directed = directed)

# IMPORTANT: igraph reads an edge attribute called "weight" automatically.
# For path-based measures (betweenness, closeness, harmonic) igraph treats the
# weight as a DISTANCE (cost). Our weights mean "stronger tie", so we create a
# distance = 1 / weight and always say which one we want.
E(g)$distance <- 1 / E(g)$weight

# Undirected copy (sum the weights when A->B and B->A are merged)
u <- if (directed) as_undirected(g, mode = "collapse",
                                 edge.attr.comb = list(weight = "sum", "ignore")) else g
E(u)$distance <- 1 / E(u)$weight

# -----------------------------------------------------------------------------
# STEP 3. Describe the whole network
# -----------------------------------------------------------------------------
cat("\n--- Network description ---\n")
cat("Nodes:", vcount(g), " Edges:", ecount(g), "\n")
cat("Density:", round(edge_density(g), 4), "\n")
cat("Isolates:", sum(degree(g) == 0), "\n")
comp <- components(u)
cat("Connected components:", comp$no, "| largest:", max(comp$csize), "\n")
cat("Transitivity (global):", round(transitivity(u, type = "global"), 3), "\n")
# isolates = "zero": nodes with fewer than 2 neighbours count as 0 (same rule as networkx)
cat("Average local clustering:", round(transitivity(u, type = "average", isolates = "zero"), 3), "\n")
if (directed) {
  cat("Reciprocity:", round(reciprocity(g), 3), "\n")
  cat("Strongly connected components:", components(g, mode = "strong")$no, "\n")
}
cat("Average shortest path (connected pairs):",
    round(mean_distance(u, weights = NA, unconnected = TRUE), 2), "\n")

deg_vec <- degree(g, mode = if (directed) "in" else "all")
p <- ggplot(data.frame(d = deg_vec), aes(d)) +
  geom_histogram(binwidth = 1, fill = "#2a78d6", colour = "#fcfcfb") +
  labs(x = if (directed) "in-degree" else "degree", y = "number of nodes",
       title = "Degree distribution") +
  theme_minimal()
ggsave(file.path(out_dir, "degree_distribution.png"), p, width = 6, height = 3.5, dpi = 150)

# -----------------------------------------------------------------------------
# STEP 4. Centrality
# -----------------------------------------------------------------------------
cent <- tibble(id = V(g)$name)
if (directed) {
  cent$in_degree   <- degree(g, mode = "in")
  cent$out_degree  <- degree(g, mode = "out")
  cent$in_strength <- strength(g, mode = "in", weights = E(g)$weight)
} else {
  cent$degree   <- degree(g)
  cent$strength <- strength(g, weights = E(g)$weight)
}
cent$betweenness   <- betweenness(g, directed = directed, weights = NA, normalized = TRUE)
cent$betweenness_w <- betweenness(g, directed = directed, weights = E(g)$distance, normalized = TRUE)
cent$closeness     <- closeness(u, weights = NA, normalized = TRUE)   # NaN for isolates
cent$harmonic      <- harmonic_centrality(u, weights = NA)
cent$eigenvector   <- eigen_centrality(u, weights = E(u)$weight)$vector
cent$pagerank      <- page_rank(g, damping = 0.85, weights = E(g)$weight)$vector

cent <- left_join(nodes, cent, by = "id")
measures <- intersect(c("in_degree", "degree", "strength", "in_strength", "betweenness",
                        "closeness", "harmonic", "eigenvector", "pagerank"), names(cent))
for (m in measures) {
  cat("\nTop 5 by", m, ":\n")
  print(cent |> arrange(desc(.data[[m]])) |> select(id, all_of(m)) |> head(5))
}
cat("\nSpearman correlation between measures:\n")
print(round(cor(cent[, measures], method = "spearman", use = "pairwise.complete.obs"), 2))

# -----------------------------------------------------------------------------
# STEP 5. Reciprocity (directed networks only)
# -----------------------------------------------------------------------------
if (directed) {
  pair_key <- paste(edges$source, edges$target)
  back_key <- paste(edges$target, edges$source)
  edges$reciprocated <- back_key %in% pair_key
  cat("\nShare of ties that are reciprocated:", round(mean(edges$reciprocated), 3), "\n")
  node_recip <- edges |> group_by(source) |>
    summarise(reciprocity = mean(reciprocated), .groups = "drop")
  cent <- left_join(cent, node_recip, by = c("id" = "source"))
  print(summary(node_recip$reciprocity))
}

# -----------------------------------------------------------------------------
# STEP 6. Clusters: k-cores and communities
# -----------------------------------------------------------------------------
cent$k_core <- coreness(u)
cat("\nLargest k-core:", max(cent$k_core), "with", sum(cent$k_core == max(cent$k_core)), "nodes\n")
set.seed(42)
comm <- cluster_louvain(u, weights = E(u)$weight)
cent$community <- as.integer(membership(comm))
cat("Louvain communities:", length(comm), "| modularity Q =",
    round(modularity(u, membership(comm), weights = E(u)$weight), 3), "\n")
print(head(table(community = cent$community, attribute = cent[[color_by]], useNA = "ifany"), 12))

# -----------------------------------------------------------------------------
# STEP 7. Homophily
# -----------------------------------------------------------------------------
keep <- V(g)$name[!is.na(vertex_attr(g, color_by))]
gs <- induced_subgraph(g, keep)
types <- as.integer(factor(vertex_attr(gs, color_by)))
r <- assortativity_nominal(gs, types = types, directed = directed)
cat("\nAssortativity by", color_by, ":", round(r, 3), "\n")
el <- as_edgelist(gs)
a1 <- vertex_attr(gs, color_by)[match(el[, 1], V(gs)$name)]
a2 <- vertex_attr(gs, color_by)[match(el[, 2], V(gs)$name)]
ei <- (sum(a1 != a2) - sum(a1 == a2)) / length(a1)
cat("E-I index:", round(ei, 3), "\n")

# -----------------------------------------------------------------------------
# STEP 8. Draw the network (ggraph)
# -----------------------------------------------------------------------------
palette3 <- c("#2a78d6", "#eb6834", "#1baf7a")
grp <- as.character(vertex_attr(g, color_by))
top3 <- names(sort(table(grp), decreasing = TRUE))[1:min(3, length(unique(na.omit(grp))))]
grp_plot <- ifelse(is.na(grp), "missing", ifelse(grp %in% top3, grp, "other"))
size_by <- if (directed) cent$pagerank else cent$degree
tg <- as_tbl_graph(u) |>
  activate(nodes) |>
  mutate(group = grp_plot, size = size_by[match(name, cent$id)])
set.seed(7)
p <- ggraph(tg, layout = "fr") +
  geom_edge_link(colour = "#c3c2b7", alpha = 0.3, linewidth = 0.25) +
  geom_node_point(aes(colour = group, size = size)) +
  scale_colour_manual(values = c(setNames(palette3[seq_along(top3)], top3),
                                 other = "#b5b3ab", missing = "#b5b3ab")) +
  scale_size(range = c(0.5, 6), guide = "none") +
  labs(title = dataset, colour = color_by) +
  theme_void()
ggsave(file.path(out_dir, "network.png"), p, width = 9, height = 8, dpi = 150, bg = "#fcfcfb")

# -----------------------------------------------------------------------------
# STEP 9. Save results
# -----------------------------------------------------------------------------
write_csv(cent, file.path(out_dir, "node_results.csv"))
V(g)$community   <- cent$community[match(V(g)$name, cent$id)]
V(g)$pagerank    <- cent$pagerank[match(V(g)$name, cent$id)]
V(g)$betweenness <- cent$betweenness[match(V(g)$name, cent$id)]
write_graph(g, file.path(out_dir, "network_with_results.graphml"), format = "graphml")
cat("\nSaved figures and tables in", out_dir, "\n")
