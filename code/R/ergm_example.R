# =============================================================================
# Going further: an exponential random graph model (ERGM) with statnet
# Question: are friendship ties more likely between students of the same grade,
# gender and team, and are they more likely to be reciprocated than by chance?
# install.packages(c("ergm", "network", "intergraph", "igraph", "readr"))
# =============================================================================
suppressPackageStartupMessages({
  library(igraph); library(readr); library(intergraph); library(network); library(ergm)
})
base <- file.path("..", "..", "data", "01_school_vaping")
nodes <- read_csv(file.path(base, "nodes.csv"), show_col_types = FALSE)
edges <- read_csv(file.path(base, "edges.csv"), show_col_types = FALSE)
g   <- graph_from_data_frame(edges, vertices = nodes, directed = TRUE)
net <- asNetwork(g)          # igraph -> statnet "network" object

# "none" (no team) should not count as "same team"
teams <- sort(unique(nodes$team_club))
no_team <- which(teams == "none")

# Model 1: homophily only (fast, a few seconds)
m1 <- ergm(net ~ edges + nodematch("grade") + nodematch("gender") +
             nodematch("team_club", levels = -no_team))
summary(m1)

# Model 2: add reciprocity ("mutual"). Uses MCMC, about 1-2 minutes.
m2 <- ergm(net ~ edges + mutual + nodematch("grade") + nodematch("gender") +
             nodematch("team_club", levels = -no_team),
           control = control.ergm(seed = 42))
summary(m2)
round(exp(coef(m2)), 2)      # odds ratios (conditional on the rest of the network)
# mcmc.diagnostics(m2)       # check convergence
