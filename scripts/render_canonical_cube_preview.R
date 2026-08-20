args <- commandArgs(trailingOnly = TRUE)

if (length(args) != 2L) {
  stop(
    "Usage: render_canonical_cube_preview.R READ_SET_JSON OUTPUT_SVG",
    call. = FALSE
  )
}

read_set_path <- args[[1L]]
output_path <- args[[2L]]

if (!requireNamespace("jsonlite", quietly = TRUE)) {
  stop("The jsonlite package is required.", call. = FALSE)
}
if (!requireNamespace("backgammoncalculator", quietly = TRUE)) {
  stop("The backgammoncalculator package is required.", call. = FALSE)
}
if (!requireNamespace("backgammonboard", quietly = TRUE)) {
  stop("The backgammonboard package is required.", call. = FALSE)
}

suppressPackageStartupMessages(library(backgammonboard))

document <- jsonlite::fromJSON(read_set_path, simplifyVector = FALSE)
stopifnot(length(document$analyses) == 1L)
analysis <- document$analyses[[1L]]
stopifnot(identical(analysis$decision_kind, "cube"))

source <- analysis$source_occurrence
gnu_position_id <- source$gnu_position_id_native
gnu_match_id <- source$gnu_match_id_native

if (
  !is.character(gnu_position_id) || length(gnu_position_id) != 1L ||
  !nzchar(gnu_position_id) ||
  !is.character(gnu_match_id) || length(gnu_match_id) != 1L ||
  !nzchar(gnu_match_id)
) {
  stop("Canonical cube read set is missing source-native GNU IDs.", call. = FALSE)
}

complete_gnuid <- paste0(gnu_position_id, ":", gnu_match_id)
xgid <- backgammoncalculator::gnuid_to_xgid(complete_gnuid)
position <- backgammon_position(xgid)
context <- analysis$context

other_player <- setdiff(c("player_0", "player_1"), position$on_roll)
stopifnot(
  length(other_player) == 1L,
  identical(as.integer(position$match_length), as.integer(context$score$match_length)),
  identical(
    as.integer(position$score[[position$on_roll]]),
    as.integer(context$score$player)
  ),
  identical(
    as.integer(position$score[[other_player]]),
    as.integer(context$score$opponent)
  ),
  identical(as.integer(position$cube_value), as.integer(context$cube$value)),
  identical(context$cube$owner, "centered"),
  identical(position$cube_owner, "center")
)

dir.create(dirname(output_path), recursive = TRUE, showWarnings = FALSE)

plot <- ggboard(
  position,
  colors = board_colors("bs"),
  style = board_style("bs"),
  perspective = "decision_maker",
  light_player = "near_player",
  player_name_style = "checker"
)

grDevices::svg(output_path, width = 10.625, height = 7.5, bg = "white")
print(plot)
grDevices::dev.off()

stopifnot(file.exists(output_path), file.info(output_path)$size > 0)

message(
  paste0(
    "PASS: rendered Canonical cube board from GNUID ",
    complete_gnuid,
    " (XGID ",
    xgid,
    ")"
  )
)
