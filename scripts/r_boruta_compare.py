"""Local comparison of R Boruta (ranger Extra Trees) against Bankai Boruta.

Both sides share the profile's trees, depth and feature fraction, bootstrap,
one random threshold per candidate feature, impurity importance, perc=100
(max shadow), Bonferroni over all features at alpha (Bankai two_step=False,
R mcAdj=TRUE) and at most MAX_ROUNDS rounds. Every fit runs in a fresh process
on the same float32 training matrix, methods rotate across seeds, and fit time
covers only the selector's fit. Precision and recall use the generator's
relevant features; AUC is the suite's downstream ExtraTrees on the confirmed set.

Usage: python scripts/r_boruta_compare.py OUTPUT_JSONL PROFILES SEEDS [--mode smoke-matrix] [--threads N]
       [--methods r_ranger,bankai_exact] [--max-rounds 40] [--alpha 0.05]
"""
import argparse
import gc
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bankai_benchmark.config import profile  # noqa: E402
from bankai_benchmark.datasets import generate_dataset  # noqa: E402
from bankai_benchmark.metrics import downstream  # noqa: E402


def bankai_fit(prefix, rows, cols, seed, threads, cfg, max_rounds, alpha, binned):
    import time
    from bankai_boruta import BankaiBoruta
    from bankai_random_forest import BankaiRandomForestClassifier
    X = np.fromfile(f"{prefix}-X.f32", dtype="<f4").reshape(rows, cols)
    y = np.fromfile(f"{prefix}-y.i32", dtype="<i4")
    forest = BankaiRandomForestClassifier(n_estimators=cfg.trees, max_depth=cfg.depth,
        max_features=cfg.max_features, bootstrap=True, n_jobs=threads, random_state=seed, extra_trees=True,
        extra_trees_backend="binned" if binned else "exact", max_bins=cfg.bins if binned else None)
    # BankaiBoruta mirrors BorutaPy: max_iter + 1 allows max_iter rounds.
    model = BankaiBoruta(estimator=forest, n_estimators=cfg.trees, perc=100, alpha=alpha, two_step=False,
        max_iter=max_rounds + 1, random_state=seed)
    started = time.perf_counter()
    model.fit(X, y)
    seconds = time.perf_counter() - started
    return dict(seconds=seconds, rounds=int(model.n_iter_), support=np.flatnonzero(model.support_).tolist(),
        bankai_boruta=importlib.metadata.version("bankai-boruta"),
        bankai_random_forest=importlib.metadata.version("bankai-random-forest"))


def run(method, prefix, rows, cols, seed, threads, cfg, mode, max_rounds, alpha):
    if method == "r_ranger":
        command = ["Rscript", str(ROOT / "scripts" / "r_boruta_fit.R"), prefix, rows, cols, seed, threads,
                   cfg.trees, cfg.depth, cfg.max_features, max_rounds, alpha]
    else:
        command = [sys.executable, __file__, "--worker", method, prefix, rows, cols, seed, threads, cfg.dataset,
                   mode, max_rounds, alpha]
    done = subprocess.run(list(map(str, command)), capture_output=True, text=True)
    if done.returncode:
        raise RuntimeError(f"{method} failed:\n{done.stderr[-4000:]}")
    return json.loads(done.stdout.strip().splitlines()[-1])


def worker(argv):
    method, prefix, rows, cols, seed, threads, name, mode, max_rounds, alpha = argv
    result = bankai_fit(prefix, int(rows), int(cols), int(seed), int(threads), profile(name, mode),
        int(max_rounds), float(alpha), method == "bankai_binned")
    print(json.dumps(result))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("profiles")
    parser.add_argument("seeds")
    parser.add_argument("--mode", default="full", help="generator size: full or smoke-matrix (5%% rows, 30%% columns)")
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--methods", default="r_ranger,bankai_exact")
    parser.add_argument("--max-rounds", type=int, default=40)
    parser.add_argument("--alpha", type=float, default=.05)
    args = parser.parse_args()
    methods = args.methods.split(",")
    output = Path(args.output)
    done = set()
    if output.exists():
        done = {(r["dataset"], r["seed"], r["method"]) for r in map(json.loads, output.read_text().splitlines())}
    for name in args.profiles.split(","):
        cfg = profile(name, args.mode)
        for index, seed in enumerate(map(int, args.seeds.split(","))):
            order = methods[index % len(methods):] + methods[:index % len(methods)]
            pending = [m for m in order if (name, seed, m) not in done]
            if not pending:
                continue
            bundle = generate_dataset(name, seed, args.mode)
            relevant = {int(i) for i in bundle.relevant_features}
            X = np.ascontiguousarray(bundle.X_train, dtype="<f4")
            y = np.asarray(bundle.y_train, dtype="<i4")
            rows, cols = X.shape
            data_hash = hashlib.sha256(X.tobytes() + y.tobytes()).hexdigest()
            with tempfile.TemporaryDirectory() as folder:
                prefix = f"{folder}/data"
                X.tofile(f"{prefix}-X.f32")
                y.tofile(f"{prefix}-y.i32")
                del X, y
                gc.collect()
                for method in pending:
                    fit = run(method, prefix, rows, cols, seed, args.threads, cfg, args.mode, args.max_rounds, args.alpha)
                    support = fit["support"]
                    hits = len(relevant & set(support))
                    # Downstream AUC runs outside the timed fit.
                    record = dict(dataset=name, mode=args.mode, seed=seed, method=method, rows=rows, cols=cols,
                        data_sha256=data_hash, threads=args.threads, trees=cfg.trees, depth=cfg.depth,
                        max_features=cfg.max_features, alpha=args.alpha, max_rounds=args.max_rounds,
                        seconds=round(fit["seconds"], 2), rounds=fit["rounds"], confirmed=len(support),
                        precision=hits / len(support) if support else None, recall=hits / len(relevant),
                        auc=downstream(bundle, np.asarray(support, dtype=int), seed, args.threads)["roc_auc"],
                        support=support, versions={k: v for k, v in fit.items() if k not in {"seconds", "rounds", "support"}})
                    with output.open("a") as handle:
                        handle.write(json.dumps(record) + "\n")
                    print(json.dumps({k: record[k] for k in ("dataset", "seed", "method", "seconds", "rounds",
                        "confirmed", "precision", "recall", "auc")}), flush=True)
            del bundle
            gc.collect()


if __name__ == "__main__":
    if sys.argv[1:2] == ["--worker"]:
        worker(sys.argv[2:])
    else:
        main()
