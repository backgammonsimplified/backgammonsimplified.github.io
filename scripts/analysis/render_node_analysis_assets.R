args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1L) {
  stop("Usage: render_node_analysis_assets.R RENDER_MANIFEST", call. = FALSE)
}

for (package in c("jsonlite", "backgammoncalculator", "backgammonboard")) {
  if (!requireNamespace(package, quietly = TRUE)) {
    stop(paste0("Required R package is unavailable: ", package), call. = FALSE)
  }
}
suppressPackageStartupMessages(library(backgammonboard))

node_schema <- paste0("b", "ms-node-analysis-view-v0")
manifest <- jsonlite::fromJSON(args[[1L]], simplifyVector = FALSE)
stopifnot(
  identical(manifest$schema_version, "bs-local-node-analysis-authoring-v1"),
  identical(manifest$authority, "local-development-only"),
  is.character(manifest$output_root),
  length(manifest$analyses) > 0L
)

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
  if (any(lengths(pieces) != 3L)) return(NULL)
  board_moves(
    from = vapply(pieces, function(piece) as.integer(piece[[2L]]), integer(1L)),
    to = vapply(pieces, function(piece) as.integer(piece[[3L]]), integer(1L)),
    die = rep(NA_integer_, length(tokens)),
    label = tokens
  )
}

provenance <- c(
  "Local Node analysis authoring assets",
  "====================================",
  "",
  "authority: local-development-only",
  "canonical_authority: false",
  paste0("slug: ", manifest$slug),
  ""
)

seen_ids <- character()
seen_subdirs <- character()
for (entry in manifest$analyses) {
  source <- jsonlite::fromJSON(entry$artifact, simplifyVector = FALSE)
  stopifnot(
    identical(source$schema_version, node_schema),
    identical(source$analysis_key, entry$analysis_id),
    identical(source$analysis_kind, entry$kind),
    !entry$analysis_id %in% seen_ids,
    !entry$asset_subdir %in% seen_subdirs
  )
  seen_ids <- c(seen_ids, entry$analysis_id)
  seen_subdirs <- c(seen_subdirs, entry$asset_subdir)
  output_dir <- file.path(manifest$output_root, entry$asset_subdir)
  position <- source$source_request$position$id
  decision <- if (identical(entry$kind, "checker")) "checker_play" else "roll_double"
  starting <- ggboard(
    position,
    colors = board_colors("bs"),
    style = board_style("bs"),
    decision = decision,
    perspective = "decision_maker",
    light_player = "near_player",
    player_name_style = "checker"
  )
  save_svg(starting, file.path(output_dir, "starting.svg"))

  rendered <- 0L
  if (identical(entry$kind, "checker")) {
    source_by_id <- setNames(source$checker$candidates, vapply(source$checker$candidates, `[[`, character(1L), "id"))
    for (candidate in entry$candidates) {
      stopifnot(candidate$id %in% names(source_by_id))
      source_candidate <- source_by_id[[candidate$id]]
      stopifnot(identical(source_candidate$notation, candidate$notation))
      moves <- simple_moves(candidate$notation)
      if (is.null(candidate$filename)) {
        stopifnot(is.null(moves))
        next
      }
      stopifnot(!is.null(moves), identical(basename(candidate$filename), candidate$filename))
      plot <- ggboard(
        position,
        colors = board_colors("bs"),
        style = board_style("bs"),
        moves = moves,
        decision = "checker_play",
        perspective = "decision_maker",
        light_player = "near_player",
        player_name_style = "checker"
      )
      save_svg(plot, file.path(output_dir, candidate$filename))
      rendered <- rendered + 1L
    }
  } else if (isTRUE(entry$render_responder_board)) {
    starting_position <- attr(starting, "backgammon_position")
    offered_xgid <- sub(":00:", ":D:", starting_position$xgid, fixed = TRUE)
    if (identical(offered_xgid, starting_position$xgid)) {
      stop("Cube position cannot be unambiguously prepared as an offered double", call. = FALSE)
    }
    responder <- ggboard(
      offered_xgid,
      colors = board_colors("bs"),
      style = board_style("bs"),
      decision = "take_pass",
      perspective = "decision_maker",
      light_player = "near_player",
      player_name_style = "checker"
    )
    responder_position <- attr(responder, "backgammon_position")
    stopifnot(
      identical(starting_position$points, responder_position$points),
      identical(starting_position$bar, responder_position$bar),
      identical(starting_position$off, responder_position$off),
      identical(starting_position$on_roll, responder_position$on_roll),
      identical(starting_position$cube_value, responder_position$cube_value),
      identical(starting_position$cube_owner, responder_position$cube_owner),
      identical(starting_position$score, responder_position$score),
      !identical(attr(responder, "backgammon_near_player"), responder_position$on_roll)
    )
    save_svg(responder, file.path(output_dir, "responder.svg"))
  }
  provenance <- c(
    provenance,
    paste0("analysis_key: ", entry$analysis_id),
    paste0("analysis_kind: ", entry$kind),
    paste0("artifact_sha256: ", entry$artifact_sha256),
    paste0("gnuid: ", position),
    paste0("checker_overlays_rendered: ", rendered),
    ""
  )
}
provenance <- c(
  provenance,
  "All boards are build-time presentation assets.",
  "The browser does not run an engine, interpret a position, or apply moves."
)
writeLines(provenance, file.path(manifest$output_root, "PROVENANCE.txt"), useBytes = TRUE)
message("PASS: rendered local Node board assets without running an analysis engine.")
