args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 4L) {
  stop(
    paste(
      "Usage: render_real_checker_assets.R",
      "FIXTURE_DIR PROJECTION_JSON BACKGAMMONBOARD_REPO OUTPUT_DIR"
    ),
    call. = FALSE
  )
}

fixture_dir <- args[[1L]]
projection_path <- args[[2L]]
board_repo <- args[[3L]]
output_dir <- args[[4L]]
calculator_repo <- Sys.getenv("BACKGAMMONCALCULATOR_REPO", unset = "")

if (!requireNamespace("jsonlite", quietly = TRUE)) {
  stop("The jsonlite package is required; rerun the repository setup command.", call. = FALSE)
}
if (!requireNamespace("backgammoncalculator", quietly = TRUE)) {
  stop(
    "The local backgammoncalculator package is not installed; rerun the retained checker render wrapper.",
    call. = FALSE
  )
}
if (!requireNamespace("backgammonboard", quietly = TRUE)) {
  stop(
    "The local backgammonboard package is not installed; rerun the retained checker render wrapper.",
    call. = FALSE
  )
}
suppressPackageStartupMessages(library(backgammonboard))

repo_commit <- function(path, label) {
  if (!nzchar(path) || !dir.exists(path)) {
    stop(paste0("Unable to locate ", label, " checkout for provenance."), call. = FALSE)
  }
  value <- trimws(system2(
    "git",
    c("-C", normalizePath(path, winslash = "/"), "rev-parse", "HEAD"),
    stdout = TRUE
  ))
  if (length(value) != 1L || !grepl("^[0-9a-f]{40}$", value)) {
    stop(paste0("Unable to record exact ", label, " commit."), call. = FALSE)
  }
  value
}

board_commit <- repo_commit(board_repo, "Backgammonboard")
calculator_commit <- repo_commit(calculator_repo, "Backgammoncalculator")

read_object <- function(path) {
  jsonlite::fromJSON(path, simplifyVector = FALSE)
}

position_document <- read_object(file.path(fixture_dir, "position.json"))
analysis_document <- read_object(file.path(fixture_dir, "analysis.json"))
view_document <- read_object(file.path(fixture_dir, "analyzer-view.json"))
projection <- read_object(projection_path)
fixture_id <- view_document$position_id
lesson_fixture <- projection$checker_cases[[fixture_id]]

stopifnot(
  identical(position_document$position_id, view_document$position_id),
  identical(analysis_document$analysis_id, view_document$analysis_id),
  identical(lesson_fixture$position_id, view_document$position_id),
  identical(lesson_fixture$state_hash, view_document$state_hash),
  identical(lesson_fixture$analysis_id, view_document$analysis_id)
)

# The retained fixture's source GNU Position ID and Match ID are authoritative.
# Derive the complete XGID through backgammoncalculator instead of maintaining a
# second hand-coded position string in the website renderer.
source <- position_document$source
gnu_position_id <- source$gnu_position_id
gnu_match_id <- source$gnu_match_id
if (
  !is.character(gnu_position_id) || length(gnu_position_id) != 1L ||
  !is.character(gnu_match_id) || length(gnu_match_id) != 1L
) {
  stop("Retained position.json is missing its authoritative GNU Position/Match IDs.", call. = FALSE)
}
complete_gnuid <- paste0(gnu_position_id, ":", gnu_match_id)
starting_xgid <- backgammoncalculator::gnuid_to_xgid(complete_gnuid)
position <- backgammon_position(starting_xgid)
state <- position_document$state

# These context checks make the source conversion fail closed if player identity
# or match metadata ever diverges from the retained structured position.
stopifnot(
  position$on_roll %in% c("player_0", "player_1"),
  identical(as.integer(position$dice), as.integer(unlist(state$dice))),
  identical(as.integer(position$cube_value), as.integer(state$cube$value)),
  identical(position$cube_owner, "center"),
  identical(as.integer(position$score[[position$on_roll]]), as.integer(state$score$player)),
  identical(
    as.integer(position$score[[setdiff(c("player_0", "player_1"), position$on_roll)]]),
    as.integer(state$score$opponent)
  ),
  identical(as.integer(position$match_length), as.integer(state$score$match_length))
)

position_to_decision_player_arrangement <- function(position) {
  stopifnot(inherits(position, "backgammon_position"))
  decision_player <- position$on_roll
  opponent_player <- setdiff(c("player_0", "player_1"), decision_player)
  stopifnot(
    length(decision_player) == 1L,
    decision_player %in% c("player_0", "player_1"),
    length(opponent_player) == 1L
  )
  player <- integer(25L)
  opponent <- integer(25L)
  for (point in seq_len(24L)) {
    player_point <- if (identical(decision_player, "player_1")) point else 25L - point
    opponent_point <- if (identical(opponent_player, "player_1")) point else 25L - point
    player[[player_point]] <- if (identical(decision_player, "player_1")) {
      max(position$points[[point]], 0L)
    } else {
      max(-position$points[[point]], 0L)
    }
    opponent[[opponent_point]] <- if (identical(opponent_player, "player_1")) {
      max(position$points[[point]], 0L)
    } else {
      max(-position$points[[point]], 0L)
    }
  }
  player[[25L]] <- unname(position$bar[[decision_player]])
  opponent[[25L]] <- unname(position$bar[[opponent_player]])
  list(
    player_borne_off = unname(position$off[[decision_player]]),
    player_points_1_to_24_and_bar = as.list(player),
    opponent_borne_off = unname(position$off[[opponent_player]]),
    opponent_points_1_to_24_and_bar = as.list(opponent),
    perspective = "decision_player"
  )
}

arrangements_equal <- function(actual, expected) {
  identical(actual$perspective, expected$perspective) &&
    identical(as.integer(actual$player_borne_off), as.integer(expected$player_borne_off)) &&
    identical(as.integer(actual$opponent_borne_off), as.integer(expected$opponent_borne_off)) &&
    identical(
      as.integer(unlist(actual$player_points_1_to_24_and_bar)),
      as.integer(unlist(expected$player_points_1_to_24_and_bar))
    ) &&
    identical(
      as.integer(unlist(actual$opponent_points_1_to_24_and_bar)),
      as.integer(unlist(expected$opponent_points_1_to_24_and_bar))
    )
}

if (!arrangements_equal(
  position_to_decision_player_arrangement(position),
  position_document$state$checker_arrangement
)) {
  stop(
    paste0(
      "GNUID-derived starting position does not match position.json. GNUID: ",
      complete_gnuid,
      " XGID: ",
      starting_xgid
    ),
    call. = FALSE
  )
}

# Current backgammonboard deliberately does not parse GNU/source move notation.
# This bounded retained fixture uses only normalized point-to-point tokens. Turn
# those tokens into ordered board_moves() rows and leave die=NA so the renderer
# does not invent a die assignment for collapsed notation such as 8/4. The
# resulting checker arrangement is validated below against analyzer-view.json.
structured_moves_from_fixture_notation <- function(move_text) {
  if (!is.character(move_text) || length(move_text) != 1L || !nzchar(trimws(move_text))) {
    stop("Candidate move must be one non-empty normalized move string.", call. = FALSE)
  }
  tokens <- strsplit(trimws(move_text), "[[:space:]]+")[[1L]]
  matches <- regexec("^([1-9]|1[0-9]|2[0-4])/([1-9]|1[0-9]|2[0-4])$", tokens)
  pieces <- regmatches(tokens, matches)
  if (any(lengths(pieces) != 3L)) {
    stop(
      paste0(
        "This retained preview renderer only accepts simple point-to-point tokens; got: ",
        move_text
      ),
      call. = FALSE
    )
  }
  from <- vapply(pieces, function(piece) as.integer(piece[[2L]]), integer(1L))
  to <- vapply(pieces, function(piece) as.integer(piece[[3L]]), integer(1L))
  board_moves(
    from = from,
    to = to,
    die = rep(NA_integer_, length(from)),
    label = tokens
  )
}

save_svg <- function(plot, path) {
  grDevices::svg(path, width = 10.625, height = 7.5, bg = "white")
  print(plot)
  grDevices::dev.off()
  stopifnot(file.exists(path), file.info(path)$size > 0)
}

dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

starting <- ggboard(
  position,
  colors = board_colors("bs"),
  style = board_style("bs"),
  decision = "checker_play",
  perspective = "decision_maker",
  light_player = "near_player",
  player_name_style = "checker"
)
save_svg(starting, file.path(output_dir, lesson_fixture$initial$image))

view_by_rank <- setNames(
  view_document$candidates,
  vapply(view_document$candidates, function(item) as.character(item$rank), character(1L))
)

for (candidate in lesson_fixture$candidates) {
  source_candidate <- view_by_rank[[as.character(candidate$rank)]]
  stopifnot(
    identical(candidate$move, source_candidate$move),
    identical(candidate$resulting_position_id, source_candidate$resulting_position_id)
  )
  moves <- structured_moves_from_fixture_notation(candidate$move)
  plot <- ggboard(
    position,
    colors = board_colors("bs"),
    style = board_style("bs"),
    decision = "checker_play",
    perspective = "decision_maker",
    light_player = "near_player",
    player_name_style = "checker",
    moves = moves
  )
  actual <- position_to_decision_player_arrangement(
    attr(plot, "backgammon_display_position")
  )
  if (!arrangements_equal(actual, source_candidate$resulting_position)) {
    stop(
      paste0(
        "Rendered move application does not match analyzer-view for rank ",
        candidate$rank,
        ".\nActual: ",
        jsonlite::toJSON(actual, auto_unbox = TRUE),
        "\nExpected: ",
        jsonlite::toJSON(source_candidate$resulting_position, auto_unbox = TRUE)
      ),
      call. = FALSE
    )
  }
  save_svg(plot, file.path(output_dir, candidate$image))
}

writeLines(
  c(
    "Real checker lesson and Analyzer preview asset provenance",
    "========================================================",
    "",
    "Source fixture:",
    "`fixtures/real-analysis/checker-sage-gnu-disagreement-001/`",
    "",
    "Identity:",
    "",
    paste0("- position_id: ", view_document$position_id),
    paste0("- state_hash: ", view_document$state_hash),
    paste0("- analysis_id: ", view_document$analysis_id),
    paste0("- GNUID: ", complete_gnuid),
    paste0("- derived XGID: ", starting_xgid),
    paste0("- backgammoncalculator commit: ", calculator_commit),
    paste0("- backgammonboard commit: ", board_commit),
    "",
    "The starting XGID is deterministically derived from the retained GNU Position",
    "ID and Match ID. The starting SVG and all candidate SVGs are rendered from",
    "that same factual starting position. Candidate SVGs differ by structured",
    "board_moves() movement overlays only. The applied checker arrangement for",
    "every candidate is validated against analyzer-view.json before acceptance.",
    "",
    "The browser does not parse move notation or apply checker moves."
  ),
  file.path(output_dir, "PROVENANCE.txt"),
  useBytes = TRUE
)

message(
  "PASS: rendered one retained starting position and three structured candidate move overlays."
)
