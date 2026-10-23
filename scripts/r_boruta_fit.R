# One R Boruta fit with ranger Extra Trees on a dataset written by r_boruta_compare.py.
#
# Usage: Rscript r_boruta_fit.R DATA_PREFIX ROWS COLS SEED THREADS TREES DEPTH MAX_FEATURES MAX_ROUNDS ALPHA
# MAX_FEATURES is "sqrt" or a column fraction, resolved per forest like scikit-learn.
# Prints one JSON line: fit seconds, rounds and the 0-based confirmed columns.
suppressPackageStartupMessages({library(Boruta); library(ranger); library(jsonlite)})

args <- commandArgs(trailingOnly = TRUE)
prefix <- args[1]
rows <- as.integer(args[2]); cols <- as.integer(args[3]); seed <- as.integer(args[4])
threads <- as.integer(args[5]); trees <- as.integer(args[6]); depth <- as.integer(args[7])
max_features <- args[8]; max_rounds <- as.integer(args[9]); alpha <- as.numeric(args[10])

read_raw <- function(path, what, size, n) {
  con <- file(path, "rb"); on.exit(close(con))
  readBin(con, what, n = n, size = size, endian = "little")
}
x <- matrix(read_raw(paste0(prefix, "-X.f32"), "numeric", 4, rows * cols), nrow = rows, byrow = TRUE)
colnames(x) <- paste0("x", seq_len(cols) - 1)
x <- as.data.frame(x)
y <- factor(read_raw(paste0(prefix, "-y.i32"), "integer", 4, rows))

# scikit-learn's int(sqrt(n)) / int(fraction * n), floored at one column.
mtry <- if (max_features == "sqrt") function(n) max(1L, floor(sqrt(n))) else {
  fraction <- as.numeric(max_features); function(n) max(1L, floor(fraction * n))
}

# Ranger draws each forest's seed from R's RNG, so one set.seed makes the run reproducible.
set.seed(seed)
started <- Sys.time()
# Boruta stops at runs < maxRuns: maxRuns = max_rounds + 1 allows max_rounds forests.
fit <- Boruta(x, y, pValue = alpha, mcAdj = TRUE, maxRuns = max_rounds + 1, getImp = getImpRfGini,
  num.trees = trees, max.depth = depth, mtry = mtry, replace = TRUE, sample.fraction = 1,
  splitrule = "extratrees", num.random.splits = 1, num.threads = threads)
seconds <- as.numeric(difftime(Sys.time(), started, units = "secs"))

confirmed <- which(fit$finalDecision == "Confirmed") - 1L
cat(toJSON(list(seconds = seconds, rounds = nrow(fit$ImpHistory), support = I(confirmed),
  r = R.version.string,
  boruta = as.character(packageVersion("Boruta")), ranger = as.character(packageVersion("ranger"))),
  auto_unbox = TRUE), "\n")
