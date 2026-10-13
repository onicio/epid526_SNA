# Interactive network with visNetwork: install.packages("visNetwork")
suppressPackageStartupMessages({library(visNetwork); library(readr); library(dplyr); library(igraph)})
base <- file.path("..", "..", "data", "05_vaccine_conversation")
nodes <- read_csv(file.path(base, "nodes.csv"), show_col_types = FALSE)
edges <- read_csv(file.path(base, "edges.csv"), show_col_types = FALSE)
g <- graph_from_data_frame(edges, vertices = nodes, directed = TRUE)
pr <- page_rank(g, weights = E(g)$weight)$vector

vn <- nodes |> transmute(id, label = id, group = stance, title = paste(account_type, stance), value = pr[id])
ve <- edges |> transmute(from = source, to = target, value = weight, arrows = "to")
w <- visNetwork(vn, ve) |>
  visIgraphLayout(layout = "layout_with_fr") |>
  visOptions(highlightNearest = TRUE, selectedBy = "group")
w                                                    # shows in the RStudio Viewer
htmlwidgets::saveWidget(w, "vaccine_network_R.html") # or save it as a web page
