args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 3L) {
  stop(
    "Usage: render_node_k001_lesson_assets.R CHECKER_VIEW CUBE_VIEW OUTPUT_ROOT",
    call. = FALSE
  )
}

checker_path <- args[[1L]]
cube_path <- args[[2L]]
output_root <- args[[3L]]

for (package in c("jsonlite", "backgammoncalculator", "backgammonboard")) {
  if (!requireNamespace(package, quietly = TRUE)) {
    stop(paste0("Required R package is unavailable: ", package), call. = FALSE)
  }
}
suppressPackageStartupMessages(library(backgammonboard))

read_object <- function(path) {
  jsonlite::fromJSON(path, simplifyVector = FALSE)
}

save_svg <- function(plot, path) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  grDevices::svg(path, width = 10.625, height = 7.5, bg = "white")
  print(plot)
  grDevices::dev.off()
  stopifnot(file.exists(path), file.info(path)$size > 0)
}

simple_moves <- function(move_text) {
  if (!is.character(move_text) || length(move_text) != 1L || !nzchar(trimws(move_text))) {
    return(NULL)
  }
  tokens <- strsplit(trimws(move_text), "[[:space:]]+")[[1L]]
  matches <- regexec("^([1-9]|1[0-9]|2[0-4])/([1-9]|1[0-9]|2[0-4])$", tokens)
  pieces <- regmatches(tokens, matches)
  if (any(lengths(pieces) != 3L)) {
    return(NULL)
  }
  board_moves(
    from = vapply(pieces, function(piece) as.integer(piece[[2L]]), integer(1L)),
    to = vapply(pieces, function(piece) as.integer(piece[[3L]]), integer(1L)),
    die = rep(NA_integer_, length(tokens)),
    label = tokens
  )
}

checker <- read_object(checker_path)
cube <- read_object(cube_path)
stopifnot(
  identical(checker$schema_version, "bms-node-analysis-view-v0"),
  identical(checker$analysis_kind, "checker"),
  identical(checker$analysis_key, "sha256-52e8ef0da2e4090a81f0ab726370811812c20f76f31730c5e6d132e63b774f3d"),
  identical(checker$source_request$position$id, "4PPgASTgc/ABMA:cAnqAAAAAAAE"),
  identical(cube$schema_version, "bms-node-analysis-view-v0"),
  identical(cube$analysis_kind, "cube"),
  identical(cube$analysis_key, "sha256-1217f65d4a2c203e2370edb860ffaba81090a42f69d2a5fb56f5cceb64389e01"),
  identical(cube$source_request$position$id, "PAAAICMAAAAAAA:MAEAAAAAAAAE")
)

checker_dir <- file.path(output_root, "checker")
cube_dir <- file.path(output_root, "cube")
dir.create(checker_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(cube_dir, recursive = TRUE, showWarnings = FALSE)

checker_position <- checker$source_request$position$id
checker_start <- ggboard(
  checker_position,
  colors = board_colors("bs"),
  style = board_style("bs"),
  decision = "checker_play",
  perspective = "decision_maker",
  light_player = "near_player",
  player_name_style = "checker"
)
save_svg(checker_start, file.path(checker_dir, "starting.svg"))

rendered_candidates <- 0L
for (candidate in checker$checker$candidates) {
  moves <- simple_moves(candidate$notation)
  if (is.null(moves)) {
    next
  }
  plot <- ggboard(
    checker_position,
    colors = board_colors("bs"),
    style = board_style("bs"),
    moves = moves,
    decision = "checker_play",
    perspective = "decision_maker",
    light_player = "near_player",
    player_name_style = "checker"
  )
  save_svg(plot, file.path(checker_dir, paste0("candidate-", candidate$display_order, ".svg")))
  rendered_candidates <- rendered_candidates + 1L
}

cube_position <- cube$source_request$position$id
cube_start <- ggboard(
  cube_position,
  colors = board_colors("bs"),
  style = board_style("bs"),
  decision = "roll_double",
  perspective = "decision_maker",
  light_player = "near_player",
  player_name_style = "checker"
)
save_svg(cube_start, file.path(cube_dir, "starting.svg"))

writeLines(
  c(
    "Node K001 exact lesson preview",
    "===============================",
    "",
    paste0("checker_analysis_key: ", checker$analysis_key),
    paste0("checker_gnuid: ", checker$source_request$position$id),
    paste0("checker_recommendation: ", checker$recommendation$notation),
    paste0("checker_overlays_rendered: ", rendered_candidates),
    paste0("cube_analysis_key: ", cube$analysis_key),
    paste0("cube_gnuid: ", cube$source_request$position$id),
    paste0("cube_recommendation: ", cube$recommendation$label),
    "",
    "All boards are build-time presentation assets. The browser does not run an engine or apply moves."
  ),
  file.path(output_root, "PROVENANCE.txt"),
  useBytes = TRUE
)

message(paste0("PASS: rendered checker starting board, ", rendered_candidates, " checker overlays, and cube board."))
