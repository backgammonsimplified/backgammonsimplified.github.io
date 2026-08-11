#!/usr/bin/env Rscript

options(repos = c(CRAN = "https://cloud.r-project.org"))

fail <- function(...) {
  stop(sprintf(...), call. = FALSE)
}

run <- function(command, args) {
  status <- system2(command, args)
  if (!identical(status, 0L)) {
    fail("Command failed (%s): %s", status, paste(c(command, args), collapse = " "))
  }
}

script_args <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("^--file=", script_args, value = TRUE)
if (length(file_arg) != 1L) {
  fail("Unable to locate build_backgammonboard_docs.R")
}

script_path <- normalizePath(sub("^--file=", "", file_arg), mustWork = TRUE)
repo_root <- normalizePath(file.path(dirname(script_path), ".."), mustWork = TRUE)
site_root <- file.path(repo_root, "site")
site_output <- file.path(site_root, "_site")
destination <- file.path(site_output, "about", "backgammonboard")

if (!dir.exists(site_output)) {
  fail("Quarto output directory does not exist: %s", site_output)
}

for (package in c("pkgdown", "remotes")) {
  if (!requireNamespace(package, quietly = TRUE)) {
    message("Installing required R package: ", package)
    install.packages(package, quiet = TRUE)
  }
}

package_repo <- Sys.getenv(
  "BACKGAMMONBOARD_REPOSITORY",
  "https://github.com/backgammonsimplified/backgammonboard.git"
)
package_ref <- Sys.getenv("BACKGAMMONBOARD_REF", "master")
package_source <- Sys.getenv("BACKGAMMONBOARD_SOURCE", "")

workspace <- tempfile("backgammonboard-docs-")
dir.create(workspace, recursive = TRUE)
on.exit(unlink(workspace, recursive = TRUE, force = TRUE), add = TRUE)

if (nzchar(package_source)) {
  source_path <- normalizePath(package_source, mustWork = TRUE)
  package_path <- file.path(workspace, "backgammonboard")
  dir.create(package_path, recursive = TRUE)

  source_files <- list.files(
    source_path,
    all.files = TRUE,
    no.. = TRUE,
    full.names = TRUE
  )
  source_files <- source_files[basename(source_files) != ".git"]

  copied <- file.copy(source_files, package_path, recursive = TRUE)
  if (!all(copied)) {
    fail("Unable to copy local backgammonboard source into build workspace")
  }

  message("Building backgammonboard docs from local source: ", source_path)
} else {
  package_path <- file.path(workspace, "backgammonboard")
  message("Fetching backgammonboard ref ", package_ref)
  run(
    "git",
    c(
      "clone",
      "--depth", "1",
      "--branch", package_ref,
      package_repo,
      package_path
    )
  )
}

if (!file.exists(file.path(package_path, "DESCRIPTION"))) {
  fail("Fetched source is not an R package: %s", package_path)
}

message("Installing package dependencies needed for documentation")
remotes::install_deps(
  package_path,
  dependencies = c("Depends", "Imports", "LinkingTo"),
  upgrade = "never",
  quiet = TRUE
)

message("Building pkgdown documentation")
pkgdown::build_site(
  pkg = package_path,
  preview = FALSE,
  devel = FALSE,
  new_process = FALSE,
  install = TRUE,
  quiet = FALSE
)

pkgdown_output <- file.path(package_path, "docs")
if (!file.exists(file.path(pkgdown_output, "index.html"))) {
  fail("pkgdown did not produce docs/index.html")
}

unlink(destination, recursive = TRUE, force = TRUE)
dir.create(destination, recursive = TRUE, showWarnings = FALSE)

built_files <- list.files(
  pkgdown_output,
  all.files = TRUE,
  no.. = TRUE,
  full.names = TRUE
)

copied <- file.copy(built_files, destination, recursive = TRUE)
if (!all(copied)) {
  fail("Unable to copy generated package documentation into Quarto output")
}

message("backgammonboard documentation: ", destination)
