for (package in c("backgammoncalculator", "backgammonboard")) {
  if (!requireNamespace(package, quietly = TRUE)) {
    stop(paste0("Required R package is unavailable: ", package), call. = FALSE)
  }
}
suppressPackageStartupMessages(library(backgammonboard))

base_gnuid <- "4PPgASTgc/ABMA:cAnqAAAAAAAE"

expect_error <- function(expression, pattern) {
  error <- tryCatch({
    force(expression)
    NULL
  }, error = identity)
  stopifnot(inherits(error, "error"), grepl(pattern, conditionMessage(error), fixed = TRUE))
}

custom_gnuid <- function(
    mover = "player_1",
    dice = c(5L, 1L),
    player_0_points = integer(),
    player_1_points = integer(),
    player_0_bar = 0L,
    player_1_bar = 0L) {
  position <- backgammoncalculator::position_from_gnuid(base_gnuid)
  point_names <- paste0("point_", 1:24)
  values_0 <- stats::setNames(integer(24), point_names)
  values_1 <- stats::setNames(integer(24), point_names)
  if (length(player_0_points)) values_0[names(player_0_points)] <- player_0_points
  if (length(player_1_points)) values_1[names(player_1_points)] <- player_1_points
  if (sum(values_0) + player_0_bar == 0L) values_0[["point_1"]] <- 1L
  if (sum(values_1) + player_1_bar == 0L) values_1[["point_24"]] <- 1L
  position$players$player_0$points <- values_0
  position$players$player_1$points <- values_1
  position$players$player_0$bar <- as.integer(player_0_bar)
  position$players$player_1$bar <- as.integer(player_1_bar)
  position$players$player_0$off <- as.integer(15L - sum(values_0) - player_0_bar)
  position$players$player_1$off <- as.integer(15L - sum(values_1) - player_1_bar)
  position$turn$dice_owner <- mover
  position$turn$turn_owner <- mover
  position$turn$action <- "roll"
  position$turn$dice <- as.integer(dice)
  backgammoncalculator::gnuid_from_position(position)
}

apply_moves <- function(gnuid, moves) {
  plot <- ggboard(
    gnuid,
    moves = moves,
    decision = "checker_play",
    perspective = "decision_maker"
  )
  list(
    before = attr(plot, "backgammon_position"),
    after = attr(plot, "backgammon_display_position"),
    validation = attr(plot, "backgammon_move_validation")
  )
}

# Ordinary and two-die chained movement.
ordinary <- custom_gnuid(player_1_points = c(point_13 = 1L), dice = c(5L, 1L))
ordinary_result <- apply_moves(ordinary, board_moves(13, 8, die = 5))
stopifnot(ordinary_result$after$points[[8L]] == 1L)
two_step <- apply_moves(
  ordinary,
  board_moves(c(13, 8), c(8, 7), die = c(5, 1))
)
stopifnot(two_step$after$points[[7L]] == 1L)

# Four ordered atomic movements for doubles.
doubles <- custom_gnuid(
  player_1_points = c(point_13 = 4L),
  dice = c(3L, 3L)
)
doubles_result <- apply_moves(
  doubles,
  board_moves(rep(13, 4), rep(10, 4), die = rep(3, 4))
)
stopifnot(doubles_result$after$points[[10L]] == 4L)

# Hit, bar entry, bearoff, and bar followed by board movement.
hit <- custom_gnuid(
  player_0_points = c(point_8 = 1L),
  player_1_points = c(point_13 = 1L),
  dice = c(5L, 1L)
)
hit_result <- apply_moves(hit, board_moves(13, 8, die = 5))
stopifnot(hit_result$after$bar[["player_0"]] == 1L)

bar <- custom_gnuid(player_1_bar = 1L, dice = c(1L, 2L))
bar_result <- apply_moves(bar, board_moves("bar", 24, die = 1))
stopifnot(bar_result$after$bar[["player_1"]] == 0L, bar_result$after$points[[24L]] == 1L)

bearoff <- custom_gnuid(player_1_points = c(point_2 = 1L), dice = c(2L, 1L))
bearoff_result <- apply_moves(bearoff, board_moves(2, "off", die = 2))
stopifnot(bearoff_result$after$off[["player_1"]] == 15L)

bar_board <- custom_gnuid(
  player_1_points = c(point_6 = 1L),
  player_1_bar = 1L,
  dice = c(2L, 1L)
)
bar_board_result <- apply_moves(
  bar_board,
  board_moves(c("bar", "6"), c("24", "4"), die = c(1, 2))
)
stopifnot(
  bar_board_result$after$bar[["player_1"]] == 0L,
  bar_board_result$after$points[[24L]] == 1L,
  bar_board_result$after$points[[4L]] == 1L
)

# Two checkers landing on the same point preserve a stacked outcome.
stacked <- custom_gnuid(
  player_1_points = c(point_8 = 1L, point_6 = 1L),
  dice = c(4L, 2L)
)
stacked_result <- apply_moves(
  stacked,
  board_moves(c(8, 6), c(4, 4), die = c(4, 2))
)
stopifnot(stacked_result$after$points[[4L]] == 2L)

# Mover-relative points flip safely when stable player_0 is on roll.
flipped <- backgammoncalculator::position_from_gnuid(base_gnuid)
flipped$turn$dice_owner <- "player_0"
flipped$turn$turn_owner <- "player_0"
flipped$turn$dice <- c(5L, 1L)
flipped_gnuid <- backgammoncalculator::gnuid_from_position(flipped)
flipped_result <- apply_moves(flipped_gnuid, board_moves(13, 8, die = 5))
stopifnot(
  identical(flipped_result$before$on_roll, "player_0"),
  flipped_result$after$points[[12L]] == flipped_result$before$points[[12L]] + 1L,
  flipped_result$after$points[[17L]] == flipped_result$before$points[[17L]] - 1L
)

# Structural and impossible movement facts fail closed.
expect_error(board_moves(0, 1), "points 1 through 24 or `bar`")
expect_error(
  ggboard(ordinary, moves = board_moves(12, 7, die = 5)),
  "source point 12 is empty"
)
blocked <- custom_gnuid(
  player_0_points = c(point_8 = 2L),
  player_1_points = c(point_13 = 1L),
  dice = c(5L, 1L)
)
expect_error(
  ggboard(blocked, moves = board_moves(13, 8, die = 5)),
  "destination point 8 is blocked"
)

cat("PASS: ordinary, two-die, doubles, hit, bar, bearoff, bar+board, stack, perspective, and fail-closed movement proof.\n")
