# =============================================================================
# Dataset-specific recipes (R). Same questions as code/python/recipes.py
# Run all:   Rscript recipes.R          (working directory = code/R)
# Blocks between "# %% [name]" and "# %% [end]" are copied into the guide.
# =============================================================================
# %% [helper]
suppressPackageStartupMessages({
  library(igraph)
  library(readr)
  library(dplyr)
})
base <- file.path("..", "..", "data")   # or "https://raw.githubusercontent.com/USER/REPO/main/data"

load_net <- function(dataset, directed) {
  nodes <- read_csv(file.path(base, dataset, "nodes.csv"), show_col_types = FALSE)
  edges <- read_csv(file.path(base, dataset, "edges.csv"), show_col_types = FALSE)
  g <- graph_from_data_frame(edges, vertices = nodes, directed = directed)
  list(nodes = nodes, edges = edges, g = g)
}

# rank 1 = highest value (ties share the best rank)
rank_desc <- function(x) rank(-x, ties.method = "min")

# undirected copy that sums the weights of A->B and B->A
undirected_sum <- function(g) {
  as_undirected(g, mode = "collapse", edge.attr.comb = list(weight = "sum", "ignore"))
}
# %% [end]

d1 <- function() {
# %% [d1]
net <- load_net("01_school_vaping", directed = TRUE)
g <- net$g; nodes <- net$nodes; edges <- net$edges
vape <- setNames(nodes$vaped_30d, nodes$id)            # NA = absent on survey day

# (a) Mutual vs one-way friendships: do friends share vaping status?
edges$mutual <- paste(edges$target, edges$source) %in% paste(edges$source, edges$target)
e <- edges |> filter(!is.na(vape[source]), !is.na(vape[target]), vape[source] == 1)
e |> group_by(mutual) |> summarise(p_friend_vapes = mean(vape[target] == 1)) |> print()

# (b) Degrees of separation
u <- as_undirected(g, mode = "collapse")
vapers <- names(vape)[which(vape == 1)]
d <- distances(u, v = vapers, to = V(u), weights = NA)      # rows = vapers, columns = everyone
ego_vape <- vape[colnames(d)]
sep <- sapply(1:4, function(k) mean(ego_vape[col(d)[d == k]], na.rm = TRUE))
print(data.frame(distance = 1:4, p_ego_vapes = round(sep, 3)))
cat("baseline prevalence:", round(mean(vape, na.rm = TRUE), 3), "\n")

# (c) Choosing 46 peer leaders (10%)
k <- 46
set.seed(1)
scores <- list(`in-degree` = degree(g, mode = "in"),
               PageRank = page_rank(g)$vector,
               betweenness = betweenness(g, weights = NA),
               random = setNames(runif(vcount(g)), V(g)$name))
for (s in names(scores)) {
  leaders <- names(sort(scores[[s]], decreasing = TRUE))[1:k]
  reached <- unique(c(leaders, unlist(lapply(adjacent_vertices(u, leaders), names))))
  cat(sprintf("%-12s leaders reach %.0f%% of students\n", s, 100 * length(reached) / vcount(g)))
}

# (d) Perceived norm vs reality
surveyed <- nodes |> filter(completed_survey == 1)
actual <- sapply(surveyed$id, function(i) {
  f <- names(neighbors(g, i, mode = "out")); sum(vape[f] == 1, na.rm = TRUE) })
cat("perceived:", round(mean(surveyed$perceived_friends_vaping), 2),
    "| actual among nominated friends:", round(mean(actual), 2), "\n")
# %% [end]
}

d2 <- function() {
# %% [d2]
net <- load_net("02_nursing_home_flu", directed = FALSE)
g <- net$g; nodes <- net$nodes
E(g)$distance <- 1 / E(g)$weight

# (a) Close contacts only (>= 15 minutes in the week)
h <- delete_edges(g, E(g)[weight < 15])
cat("edges all / >=15 min:", ecount(g), "/", ecount(h), "\n")

# (b) Weighted betweenness (distance = 1 / minutes)
btw <- betweenness(g, weights = E(g)$distance, normalized = TRUE)
top <- names(sort(btw, decreasing = TRUE))[1:8]
nodes |> filter(id %in% top) |>
  select(id, role, unit, units_worked, employment, flu_vaccinated) |>
  mutate(btw = round(btw[id], 3)) |> arrange(desc(btw)) |> print()

# (c) Attack rates
nodes |> filter(person_type == "resident") |> group_by(unit) |>
  summarise(attack_rate = mean(flu_case), cases = sum(flu_case), n = n()) |> print()
nodes |> group_by(flu_vaccinated) |> summarise(attack_rate = mean(flu_case)) |> print()
nodes$degree <- degree(g)[nodes$id]
nodes |> mutate(q = ntile(degree, 4)) |> group_by(q) |>
  summarise(attack_rate = round(mean(flu_case), 3)) |> print()

# (d) Epidemic curve by week of onset
cases <- nodes |> filter(flu_case == 1) |>
  mutate(group = ifelse(person_type == "resident", paste("unit", unit), "staff"),
         week = (onset_day - 1) %/% 7 + 1)
print(table(cases$group, cases$week))

# (e) Staff cohorting: residents in other units reachable through one staff member
res_ids <- nodes$id[nodes$person_type == "resident"]
unit_of <- setNames(nodes$unit, nodes$id)
type_of <- setNames(nodes$person_type, nodes$id)
one_staff_away <- function(graph) {
  mean(sapply(res_ids, function(r) {
    staff <- names(neighbors(graph, r)); staff <- staff[type_of[staff] == "staff"]
    if (length(staff) == 0) return(0)
    two <- unique(unlist(lapply(staff, function(s) names(neighbors(graph, s)))))
    sum(two %in% res_ids & unit_of[two] != unit_of[r])
  }))
}
floaters <- nodes$id[nodes$role %in% c("CNA", "LPN", "RN") & grepl("\\+", nodes$units_worked)]
cat("floating nursing staff:", length(floaters), "\n")
cat("residents in other units one staff member away:", round(one_staff_away(h), 1), "->",
    round(one_staff_away(delete_vertices(h, floaters)), 1), "without floating staff\n")
# %% [end]
}

d3 <- function() {
# %% [d3]
net <- load_net("03_older_adults_support", directed = TRUE)
g <- net$g; nodes <- net$nodes; edges <- net$edges

# (a) Reciprocity by relationship and by mobility limitation
edges$reciprocated <- paste(edges$target, edges$source) %in% paste(edges$source, edges$target)
edges |> group_by(relationship) |> summarise(reciprocated = round(mean(reciprocated), 2)) |>
  arrange(reciprocated) |> print()
node_rec <- edges |> group_by(source) |> summarise(reciprocity = mean(reciprocated))
res <- nodes |> filter(node_type == "resident") |> left_join(node_rec, by = c("id" = "source"))
res |> group_by(mobility_limitation) |> summarise(reciprocity = round(mean(reciprocity, na.rm = TRUE), 2)) |> print()

# (b) Isolates
res$total_deg <- degree(g, mode = "all")[res$id]
iso <- res |> filter(total_deg == 0)
cat("isolates:", nrow(iso), "\n"); print(table(iso$neighborhood))

# (c) Ego-reported (LSNS-6) vs sociocentric ties
cat("Spearman(LSNS-6, degree):", round(cor(res$lsns6, res$total_deg, method = "spearman"), 2), "\n")

# (d) Loneliness by number of ties, and strain
res |> mutate(ties = cut(total_deg, c(-1, 0, 2, 5, 100), labels = c("0", "1-2", "3-5", "6+"))) |>
  group_by(ties) |> summarise(ucla3 = round(mean(ucla3_loneliness), 2), n = n()) |> print()
strain <- edges |> group_by(source) |> summarise(strain_total = sum(strain))
res <- res |> left_join(strain, by = c("id" = "source")) |> mutate(strain_total = coalesce(strain_total, 0))
crowd <- res |> filter(ucla3_loneliness >= 6, total_deg >= 5)
cat("lonely with 5+ ties:", nrow(crowd), "| mean strain:", round(mean(crowd$strain_total), 2),
    "vs all:", round(mean(res$strain_total), 2), "\n")

# (e) Brokers: what if the top-3 leave?
btw <- sort(betweenness(g, weights = NA), decreasing = TRUE)
print(nodes |> filter(id %in% names(btw)[1:6]) |> mutate(btw = btw[id]) |> arrange(desc(btw)) |>
        select(id, role, neighborhood, language, btw))
u <- as_undirected(g, mode = "collapse")
spanish <- res$id[res$language == "Spanish"]
english <- res$id[res$language == "English"]
steps <- function(graph) {
  d <- distances(graph, v = intersect(spanish, V(graph)$name), to = intersect(english, V(graph)$name), weights = NA)
  d[is.infinite(d)] <- NA
  round(mean(rowMeans(d, na.rm = TRUE), na.rm = TRUE), 2)
}
cat("mean steps Spanish -> English speakers:", steps(u), "->",
    steps(delete_vertices(u, names(btw)[1:3])), "without the top-3 brokers\n")
# %% [end]
}

d4 <- function() {
# %% [d4]
net <- load_net("04_social_needs_referrals", directed = TRUE)
g <- net$g; nodes <- net$nodes; edges <- net$edges

# (a) In-degree, in-strength and PageRank
t <- tibble(id = V(g)$name,
            in_degree = degree(g, mode = "in"),
            in_strength = strength(g, mode = "in", weights = E(g)$weight),
            pagerank = page_rank(g, weights = E(g)$weight)$vector) |>
  mutate(across(c(in_degree, in_strength, pagerank), rank_desc, .names = "{.col}_rank")) |>
  left_join(nodes |> select(id, org_name), by = "id")
t |> arrange(pagerank_rank) |> select(org_name, in_degree_rank, in_strength_rank, pagerank_rank) |> head(8) |> print()
t |> mutate(gain = in_degree_rank - pagerank_rank) |> arrange(desc(gain)) |>
  select(org_name, in_degree_rank, pagerank_rank) |> head(4) |> print()

# (b) Senders and receivers by organization type
tibble(id = V(g)$name, out = degree(g, mode = "out"), inn = degree(g, mode = "in")) |>
  left_join(nodes |> select(id, org_type), by = "id") |>
  group_by(org_type) |> summarise(out = mean(out), inn = mean(inn)) |> arrange(desc(out)) |> head(8) |> print()

# (c) Reciprocity by sector pair
sector <- setNames(nodes$sector, nodes$id)
edges |> mutate(reciprocated = paste(target, source) %in% paste(source, target),
                pair = paste(sector[source], "->", sector[target])) |>
  group_by(pair) |> summarise(reciprocated = round(mean(reciprocated), 2)) |> arrange(reciprocated) |> print(n = 20)

# (d) Articulation points (cut vertices)
u <- as_undirected(g, mode = "collapse")
cut <- articulation_points(u)
second_size <- sapply(cut$name, function(v) sort(components(delete_vertices(u, v))$csize, decreasing = TRUE)[2])
worst <- names(which.max(second_size))
cat("removing", nodes$org_name[nodes$id == worst], "-> components:",
    head(sort(components(delete_vertices(u, worst))$csize, decreasing = TRUE), 4), "\n")

# (e) A client calls 211: referral steps to organizations in each region
helpline <- nodes$id[nodes$org_type == "211 helpline"]
steps <- distances(g, v = helpline, mode = "out", weights = NA)[1, ]
receivers <- setdiff(V(g)$name[degree(g, mode = "in") > 0], helpline)
tibble(id = receivers, steps = steps[receivers]) |>
  left_join(nodes |> select(id, region), by = "id") |>
  group_by(region) |> summarise(one_step = mean(steps == 1), two_or_less = mean(steps <= 2),
                                unreachable = mean(is.infinite(steps))) |> print()
# %% [end]
}

d5 <- function() {
# %% [d5]
net <- load_net("05_vaccine_conversation", directed = TRUE)
g <- net$g; nodes <- net$nodes

# (a) In-degree vs PageRank
t <- tibble(id = V(g)$name, in_degree = degree(g, mode = "in"),
            pagerank = page_rank(g, weights = E(g)$weight)$vector) |>
  mutate(in_degree_rank = rank_desc(in_degree), pagerank_rank = rank_desc(pagerank)) |>
  left_join(nodes |> select(id, account_type, stance), by = "id")
t |> arrange(pagerank_rank) |> head(8) |> print()
t |> arrange(in_degree_rank) |> head(8) |> print()

# (b) Reposters of the account that falls most among the top 15 by in-degree
loser <- t |> filter(in_degree_rank <= 15) |> mutate(change = in_degree_rank - pagerank_rank) |>
  arrange(change) |> slice(1) |> pull(id)
reposters <- names(neighbors(g, loser, mode = "in"))
nodes |> filter(id %in% reposters) |> group_by(account_type) |>
  summarise(age_days = mean(account_age_days), posts_day = mean(posts_per_day),
            automation = mean(automation_score), n = n()) |> print()

# (c) Reciprocity by account type
edges <- net$edges
edges$reciprocated <- paste(edges$target, edges$source) %in% paste(edges$source, edges$target)
type_of <- setNames(nodes$account_type, nodes$id)
edges |> group_by(type = type_of[source]) |>
  summarise(reciprocity = round(mean(reciprocated), 2), ties = n()) |>
  arrange(desc(reciprocity)) |> head(5) |> print()

# (d) Eigenvector (undirected, weighted) vs PageRank
u <- undirected_sum(g)
eig <- eigen_centrality(u, weights = E(u)$weight)$vector
print(table(type_of[names(sort(eig, decreasing = TRUE))[1:10]]))
pr <- setNames(t$pagerank, t$id)
print(table(type_of[names(sort(pr, decreasing = TRUE))[1:10]]))

# (e) Hubs and authorities
hubs <- hits_scores(g, weights = E(g)$weight)$hub     # older igraph: hub_score(g)$vector
print(table(type_of[names(sort(hubs, decreasing = TRUE))[1:10]]))

# (f) Echo chambers and bridges
set.seed(42)
comm <- cluster_louvain(u, weights = E(u)$weight)
print(table(community = membership(comm), stance = nodes$stance[match(V(u)$name, nodes$id)]))
btw <- sort(betweenness(u, weights = NA, normalized = TRUE), decreasing = TRUE)[1:6]
print(nodes |> filter(id %in% names(btw)) |> mutate(btw = round(btw[id], 3)) |> arrange(desc(btw)) |>
        select(id, account_type, stance, language, btw))
# %% [end]
}

d6 <- function() {
# %% [d6]
net <- load_net("06_pwid_hiv_overdose", directed = FALSE)
g <- net$g; nodes <- net$nodes

# (a) Layers
layer <- function(col) delete_edges(g, E(g)[edge_attr(g, col) == 0])
layers <- list(`all ties` = g, `shared equipment` = layer("shared_equipment"),
               `sex partners` = layer("sex_partners"), `social support` = layer("social_support"))
for (nm in names(layers)) {
  b <- sort(betweenness(layers[[nm]], weights = NA), decreasing = TRUE)[1:3]
  cat(sprintf("%-17s edges=%4d top betweenness: %s\n", nm, ecount(layers[[nm]]),
              paste(names(b), nodes$role[match(names(b), nodes$id)], collapse = "; ")))
}

# (b) k-core and HIV
nodes$k_core <- coreness(g)[nodes$id]
print(table(k_core = nodes$k_core, hiv = nodes$hiv_status))

# (c) Remove the top bridge of the risk layer
risk <- layers[["shared equipment"]]
bridge <- names(which.max(betweenness(risk, weights = NA)))
cat("risk layer components before / after removing", bridge, ":",
    head(sort(components(risk)$csize, decreasing = TRUE), 3), "/",
    head(sort(components(delete_vertices(risk, bridge))$csize, decreasing = TRUE), 3), "\n")

# (d) Naloxone coverage
carriers <- nodes$id[nodes$carries_naloxone == 1]
pwid <- nodes |> filter(role == "PWID")
pwid$covered <- sapply(pwid$id, function(i) any(names(neighbors(g, i)) %in% carriers))
pwid |> group_by(location) |> summarise(covered = round(mean(covered), 2)) |> print()

# (e) Train 10 more people: top degree vs greedy coverage
uncovered <- pwid$id[!pwid$covered]
cands <- setdiff(pwid$id, carriers)
nb <- lapply(setNames(cands, cands), function(c) c(c, names(neighbors(g, c))))
by_degree <- names(sort(degree(g)[cands], decreasing = TRUE))[1:10]
greedy <- c(); left <- uncovered
for (i in 1:10) {
  gain <- sapply(cands, function(c) length(intersect(nb[[c]], left)))
  best <- names(which.max(gain)); greedy <- c(greedy, best); left <- setdiff(left, nb[[best]])
}
covered_by <- function(chosen) length(intersect(unique(unlist(nb[chosen])), uncovered))
cat("uncovered:", length(uncovered), "| top-degree picks cover:", covered_by(by_degree),
    "| greedy picks cover:", covered_by(greedy), "\n")
# %% [end]
}

if (sys.nframe() == 0) {
  for (f in c("d1", "d2", "d3", "d4", "d5", "d6")) {
    cat("\n", strrep("=", 70), "\n", f, "\n", strrep("=", 70), "\n")
    get(f)()
  }
}
