args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1L) {
  stop("Usage: render_analysis_enrichment_assets.R RENDER_MANIFEST", call. = FALSE)
}

for (package in c("jsonlite", "backgammoncalculator", "backgammonboard")) {
  if (!requireNamespace(package, quietly = TRUE)) {
    stop(paste0("Required R package is unavailable: ", package), call. = FALSE)
  }
}
suppressPackageStartupMessages(library(backgammonboard))

manifest <- jsonlite::fromJSON(args[[1L]], simplifyVector = FALSE)
stopifnot(
  identical(manifest$schema_version, "bs-analyzer-analysis-enrichment-render-v1"),
  identical(manifest$engine_execution_count, 0L),
  is.character(manifest$output_root),
  is.character(manifest$receipt_path),
  length(manifest$analyses) > 0L
)

save_svg <- function(plot, path) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  grDevices::svg(path, width = 10.625, height = 7.5, bg = "white")
  print(plot)
  grDevices::dev.off()
  stopifnot(file.exists(path), file.info(path)$size > 0)
}

required_scalar_text <- function(value, path) {
  if (!is.character(value) || length(value) != 1L || is.na(value) || !nzchar(value)) {
    stop(paste0(path, " must be one non-empty string"), call. = FALSE)
  }
  value
}

movement_location <- function(value, kind, path) {
  if (is.numeric(value) && length(value) == 1L && !is.na(value) &&
      value == as.integer(value) && value >= 1L && value <= 24L) {
    return(as.character(as.integer(value)))
  }
  special <- if (identical(kind, "from")) "bar" else "off"
  if (is.character(value) && length(value) == 1L && identical(value, special)) {
    return(value)
  }
  stop(paste0(path, " must be point 1..24 or ", special), call. = FALSE)
}

movement_die <- function(value, path) {
  if (is.null(value)) return(NA_integer_)
  if (!is.numeric(value) || length(value) != 1L || is.na(value) ||
      value != as.integer(value) || !value %in% 1:6) {
    stop(paste0(path, " must be null or die 1..6"), call. = FALSE)
  }
  as.integer(value)
}

stable_player <- function(render_player) {
  if (is.na(render_player)) return(NULL)
  backgammonboard:::render_player_to_project_player(render_player)
}

checker_state_from_display <- function(display) {
  list(
    coordinate_system = "physical_points_1_to_24",
    signed_points = as.list(as.integer(display$points)),
    players = list(
      player_0 = list(
        points = as.list(as.integer(pmax(-display$points, 0L))),
        bar = as.integer(display$bar[["player_0"]]),
        off = as.integer(display$off[["player_0"]])
      ),
      player_1 = list(
        points = as.list(as.integer(pmax(display$points, 0L))),
        bar = as.integer(display$bar[["player_1"]]),
        off = as.integer(display$off[["player_1"]])
      )
    )
  )
}

mover_relative_board <- function(state, mover) {
  stopifnot(mover %in% c("white", "black"))
  points <- as.integer(state$points)
  if (identical(mover, "white")) {
    player_points <- pmax(points, 0L)
    opponent_points <- rev(pmax(-points, 0L))
    opponent <- "black"
  } else {
    player_points <- rev(pmax(-points, 0L))
    opponent_points <- pmax(points, 0L)
    opponent <- "white"
  }
  list(
    perspective = "decision_player",
    opponent_points_1_to_24_and_bar = as.list(c(
      as.integer(opponent_points), as.integer(state$bar[[opponent]])
    )),
    player_points_1_to_24_and_bar = as.list(c(
      as.integer(player_points), as.integer(state$bar[[mover]])
    )),
    opponent_borne_off = as.integer(state$off[[opponent]]),
    player_borne_off = as.integer(state$off[[mover]])
  )
}

verify_prepared_relative_board <- function(actual, expected, path) {
  stopifnot(
    identical(expected$perspective, "decision_player"),
    identical(
      as.integer(unlist(actual$opponent_points_1_to_24_and_bar, use.names = FALSE)),
      as.integer(unlist(expected$opponent_points_1_to_24_and_bar, use.names = FALSE))
    ),
    identical(
      as.integer(unlist(actual$player_points_1_to_24_and_bar, use.names = FALSE)),
      as.integer(unlist(expected$player_points_1_to_24_and_bar, use.names = FALSE))
    ),
    identical(actual$opponent_borne_off, as.integer(expected$opponent_borne_off)),
    identical(actual$player_borne_off, as.integer(expected$player_borne_off))
  )
  invisible(path)
}

calculator_result_position <- function(starting_gnuid, display) {
  value <- backgammoncalculator::position_from_gnuid(starting_gnuid)
  state <- checker_state_from_display(display)
  for (player in c("player_0", "player_1")) {
    value$players[[player]]$points <- stats::setNames(
      as.integer(unlist(state$players[[player]]$points, use.names = FALSE)),
      paste0("point_", 1:24)
    )
    value$players[[player]]$bar <- state$players[[player]]$bar
    value$players[[player]]$off <- state$players[[player]]$off
  }
  mover <- value$turn$dice_owner
  next_player <- if (identical(mover, "player_0")) "player_1" else "player_0"
  value$turn$dice_owner <- next_player
  value$turn$turn_owner <- next_player
  value$turn$action <- "roll"
  value$turn$dice <- integer()
  complete_gnuid <- backgammoncalculator::gnuid_from_position(value)
  verified <- backgammoncalculator::position_from_gnuid(complete_gnuid)
  stopifnot(
    identical(verified$turn$dice_owner, next_player),
    identical(verified$turn$turn_owner, next_player),
    identical(verified$turn$action, "roll"),
    length(verified$turn$dice) == 0L
  )
  list(complete_gnuid = complete_gnuid, verified = verified, next_player = next_player)
}

hadd_position <- function(result) {
  player <- result$next_player
  opponent <- if (identical(player, "player_0")) "player_1" else "player_0"
  self <- result$verified$players[[player]]
  other <- result$verified$players[[opponent]]
  list(
    position_id = result$complete_gnuid,
    perspective = "player_on_roll",
    on_roll_points_1_to_24_and_bar = as.list(c(as.integer(self$points), as.integer(self$bar))),
    opponent_points_1_to_24_and_bar = as.list(c(as.integer(other$points), as.integer(other$bar))),
    on_roll_borne_off = as.integer(self$off),
    opponent_borne_off = as.integer(other$off)
  )
}

receipt_analyses <- list()
for (analysis in manifest$analyses) {
  source <- jsonlite::fromJSON(analysis$artifact, simplifyVector = FALSE)
  stopifnot(
    identical(source$analysis_key, analysis$analysis_id),
    identical(source$analysis_kind, "checker"),
    identical(source$source_request$position$format, "gnuid")
  )
  starting_gnuid <- required_scalar_text(
    source$source_request$position$id,
    "source_request.position.id"
  )
  message(paste0("Preparing analysis ", analysis$analysis_id, " from ", starting_gnuid))
  source_candidates <- setNames(
    source$checker$candidates,
    vapply(source$checker$candidates, `[[`, character(1L), "id")
  )
  stopifnot(length(source_candidates) == length(unique(names(source_candidates))))
  output_dir <- file.path(manifest$output_root, analysis$asset_subdir)
  starting_plot <- ggboard(
    starting_gnuid,
    colors = board_colors("bs"),
    style = board_style("bs"),
    decision = "checker_play",
    perspective = "decision_maker",
    light_player = "near_player",
    player_name_style = "checker"
  )
  save_svg(starting_plot, file.path(output_dir, "starting.svg"))
  starting_position <- attr(starting_plot, "backgammon_position")
  source_dice <- as.integer(unlist(source$source_request$dice, use.names = FALSE))
  stopifnot(
    length(source_dice) == 2L,
    identical(sort(source_dice), sort(as.integer(starting_position$dice)))
  )
  prepared <- list()

  for (candidate_index in seq_along(analysis$candidates)) {
    candidate <- analysis$candidates[[candidate_index]]
    candidate_id <- required_scalar_text(candidate$candidate_id, "candidate_id")
    message(paste0("Preparing candidate ", candidate_id))
    if (!candidate_id %in% names(source_candidates)) {
      stop(paste0("Unknown source candidate: ", candidate_id), call. = FALSE)
    }
    source_candidate <- source_candidates[[candidate_id]]
    stopifnot(identical(source_candidate$notation, candidate$source_notation))
    movements <- candidate$movement_steps
    if (!is.list(movements) || length(movements) == 0L) {
      stop(paste0("No structured movements for ", candidate_id), call. = FALSE)
    }
    orders <- vapply(movements, function(item) as.integer(item$order), integer(1L))
    if (!identical(orders, seq_along(movements))) {
      stop(paste0("Movement order is not consecutive for ", candidate_id), call. = FALSE)
    }
    from <- vapply(
      seq_along(movements),
      function(index) movement_location(movements[[index]]$from, "from", paste0(candidate_id, ".from")),
      character(1L)
    )
    to <- vapply(
      seq_along(movements),
      function(index) movement_location(movements[[index]]$to, "to", paste0(candidate_id, ".to")),
      character(1L)
    )
    die <- vapply(
      seq_along(movements),
      function(index) movement_die(movements[[index]]$die, paste0(candidate_id, ".die")),
      integer(1L)
    )
    moves <- board_moves(
      from = from,
      to = to,
      die = die,
      label = rep(candidate$source_notation, length(movements))
    )
    render_position <- backgammonboard:::as_render_position(starting_position)
    source_preparation <- candidate$source_preparation
    stopifnot(
      identical(
        source_preparation$preparer_version,
        manifest$authority$movement_preparer_version
      ),
      identical(
        source_preparation$source_reconstruction_version,
        manifest$authority$source_reconstruction_version
      ),
      identical(
        source_preparation$source_explainer_commit,
        manifest$authority$source_explainer_commit
      ),
      identical(source_preparation$source_fact_kind, "accepted_normalized_gnu_candidate_notation"),
      identical(source_preparation$normalized_notation, candidate$source_notation),
      identical(source_preparation$legality_status, "unique_legal_play"),
      identical(source_preparation$perspective, "decision_player_mover_relative"),
      identical(source_preparation$movement_steps, movements)
    )
    verify_prepared_relative_board(
      mover_relative_board(render_position, render_position$on_roll),
      source_preparation$source_board,
      paste0(candidate_id, ".source_board")
    )
    applied <- backgammonboard:::apply_board_moves(render_position, moves)
    verify_prepared_relative_board(
      mover_relative_board(applied, render_position$on_roll),
      source_preparation$result_board,
      paste0(candidate_id, ".result_board")
    )
    display <- backgammonboard:::position_after_application(starting_position, applied)
    result <- calculator_result_position(starting_gnuid, display)
    message(paste0("Derived result ", result$complete_gnuid))

    overlay_plot <- ggboard(
      starting_gnuid,
      colors = board_colors("bs"),
      style = board_style("bs"),
      moves = moves,
      after_xgid = backgammoncalculator::gnuid_to_xgid(result$complete_gnuid),
      decision = "checker_play",
      perspective = "decision_maker",
      light_player = "near_player",
      player_name_style = "checker"
    )
    result_plot <- ggboard(
      result$complete_gnuid,
      colors = board_colors("bs"),
      style = board_style("bs"),
      decision = "none",
      perspective = "decision_maker",
      light_player = "near_player",
      player_name_style = "checker"
    )
    movement_file <- paste0("candidate-", candidate$display_rank, "-movement.svg")
    result_file <- paste0("candidate-", candidate$display_rank, "-result.svg")
    save_svg(overlay_plot, file.path(output_dir, movement_file))
    save_svg(result_plot, file.path(output_dir, result_file))

    applied_rows <- lapply(seq_len(nrow(applied$applied_steps)), function(index) {
      row <- applied$applied_steps[index, , drop = FALSE]
      list(
        order = as.integer(index),
        hit = isTRUE(row$hit_confirmed[[1L]]),
        hit_player = if (isTRUE(row$hit_confirmed[[1L]])) stable_player(row$hit_player[[1L]]) else NULL,
        entered_from_bar = isTRUE(row$entered_from_bar[[1L]]),
        borne_off = isTRUE(row$borne_off[[1L]])
      )
    })
    prepared[[candidate_index]] <- list(
      candidate_id = candidate_id,
      candidate_concept_id = required_scalar_text(candidate$candidate_concept_id, "candidate_concept_id"),
      source_notation = candidate$source_notation,
      movement_steps = movements,
      source_preparation = source_preparation,
      applied_effects = applied_rows,
      source_player = starting_position$on_roll,
      source_position_id = starting_gnuid,
      result_next_player_on_roll = result$next_player,
      resulting_position_id = result$complete_gnuid,
      resulting_position_identity = list(
        format = "complete_gnuid",
        complete_gnuid = result$complete_gnuid,
        position_id = strsplit(result$complete_gnuid, ":", fixed = TRUE)[[1L]][[1L]]
      ),
      resulting_board_state = checker_state_from_display(display),
      hadd_position = hadd_position(result),
      die_validation_status = applied$die_validation_status,
      full_play_validation_status = applied$full_play_validation_status,
      movement_asset_file = movement_file,
      result_asset_file = result_file,
      perspective = list(
        movement_coordinates = "mover_relative_points",
        movement_board = "source_decision_maker",
        result_board = "post_move_next_player_on_roll"
      )
    )
  }
  receipt_analyses[[length(receipt_analyses) + 1L]] <- list(
    analysis_id = analysis$analysis_id,
    artifact_sha256 = analysis$artifact_sha256,
    source_position_id = starting_gnuid,
    starting_board_state = checker_state_from_display(starting_position),
    candidates = prepared
  )
}

receipt <- list(
  schema_version = "bs-analyzer-candidate-preview-receipt-v1",
  authority = list(
    board_repository = "backgammonsimplified/backgammonboard",
    board_commit = manifest$authority$board_commit,
    calculator_repository = "backgammonsimplified/backgammoncalculator",
    calculator_commit = manifest$authority$calculator_commit,
    movement_preparer_version = manifest$authority$movement_preparer_version,
    source_reconstruction_version = manifest$authority$source_reconstruction_version,
    source_explainer_commit = manifest$authority$source_explainer_commit
  ),
  engine_execution_count = 0L,
  deterministic = TRUE,
  analyses = receipt_analyses
)
jsonlite::write_json(receipt, manifest$receipt_path, auto_unbox = TRUE, pretty = TRUE, null = "null")
message("PASS: prepared verified candidate movement and result assets without engine execution.")
