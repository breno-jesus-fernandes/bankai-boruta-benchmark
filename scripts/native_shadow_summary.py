"""Summarize native-shadow artifacts: per-dataset medians over seeds of per-seed medians.

Usage: python scripts/native_shadow_summary.py ARTIFACT_DIR [AUC_JSON]

A directory with several thread counts (a thread sweep) gets one row per thread count.
"""
import json
from pathlib import Path
import statistics as st
import sys

METHODS = ("bankai_exact", "bankai_binned", "borutapy", "borutapy_lgbm")


def main():
    source = Path(sys.argv[1])
    auc = json.loads(Path(sys.argv[2]).read_text()) if len(sys.argv) > 2 and Path(sys.argv[2]).exists() else {}
    table = {}
    for path in sorted(source.glob("*-seed*-t*.json")):
        artifact = json.loads(path.read_text())
        assert artifact["dataset_hash_consistency"] == "passed", path
        if "auc" in artifact:
            # Real data records its held-out AUC inside the artifact.
            auc[f"{artifact['configuration']['dataset']}-{artifact['configuration']['seed']}"] = artifact["auc"]
        for result in artifact["results"]:
            key = (result.get("dataset", "industrial"), artifact["configuration"]["threads"], result["method"])
            table.setdefault(key, {}).setdefault(result["seed"], []).append(result)
    # A thread sweep keys each row by its thread count too.
    sweep = len({threads for _, threads, _ in table}) > 1
    summary = {}
    for (dataset, threads, method), seeds in sorted(table.items()):
        rows = list(seeds.values())
        seconds = [st.median(r["elapsed_seconds"] for r in rs) for rs in rows]
        rss = [st.median(r["peak_rss_delta_bytes"] for r in rs) / 2**20 for rs in rows]
        # Real data has no known relevant features and records neither metric.
        precision = [st.median(r["precision"] for r in rs) for rs in rows if "recall" in rs[0]] or [None]
        recall = [st.median(r["recall"] for r in rs) for rs in rows if "recall" in rs[0]] or [None]
        aucs = [auc[f"{dataset}-{seed}"]["by_method"][method] for seed in seeds
                if method in auc.get(f"{dataset}-{seed}", {}).get("by_method", {})]
        summary[f"{dataset}/t{threads}/{method}" if sweep else f"{dataset}/{method}"] = dict(seeds=sorted(seeds), repeats=[len(rs) for rs in rows],
            median_seconds=st.median(seconds), min_seconds=min(seconds), max_seconds=max(seconds),
            median_rss_mib=st.median(rss), min_rss_mib=min(rss), max_rss_mib=max(rss),
            rounds=[rs[0]["rounds"] for rs in rows], median_rounds=st.median(rs[0]["rounds"] for rs in rows),
            median_precision=None if precision == [None] else st.median(precision),
            min_precision=None if precision == [None] else min(precision),
            median_recall=None if recall == [None] else st.median(recall),
            min_recall=None if recall == [None] else min(recall),
            confirmed=[len(rs[0]["support"]) for rs in rows],
            median_auc=st.median(aucs) if aucs else None,
            seconds_by_seed=dict(zip(sorted(seeds), seconds)), rss_by_seed=dict(zip(sorted(seeds), rss)))
    for name, row in summary.items():
        print(f"{name:32s} t {row['median_seconds']:6.1f} [{row['min_seconds']:6.1f},{row['max_seconds']:6.1f}] "
              f"rss {row['median_rss_mib']:6.0f} rounds {row['rounds']} confirmed {row['confirmed']} "
              f"P {row['median_precision']} (min {row['min_precision']}) R {row['median_recall']} (min {row['min_recall']}) "
              f"AUC {row['median_auc']}")
    (source / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
