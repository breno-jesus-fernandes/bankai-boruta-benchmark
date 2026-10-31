"""Downstream ROC AUC for native-shadow artifacts, computed after the timed runs.

For each dataset and seed, fits the suite's downstream ExtraTrees (200 trees,
balanced classes) on every distinct confirmed set, on all features and on the
generator's relevant features, using the artifact's profile (1x or 2x).
Results are deterministic given the seed and the platform (arm64 and x86 differ
slightly), whatever the thread count.

Usage: python scripts/native_shadow_auc.py ARTIFACT_DIR OUTPUT_JSON [THREADS]
"""
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bankai_benchmark.datasets import generate_dataset  # noqa: E402
from bankai_benchmark.metrics import downstream  # noqa: E402


def main():
    source, target = Path(sys.argv[1]), Path(sys.argv[2])
    threads = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    output = json.loads(target.read_text()) if target.exists() else {}
    for path in sorted(source.glob("*-seed*-t*.json")):
        artifact = json.loads(path.read_text())
        name, seed = artifact["configuration"].get("dataset", "industrial"), artifact["configuration"]["seed"]
        key = f"{name}-{seed}"
        # Real data records its held-out AUC inside the artifact.
        if key in output or "auc" in artifact:
            continue
        # 2x artifacts record profile_mode "full2x"; older ones predate the field.
        bundle = generate_dataset(name, seed, artifact["configuration"].get("profile_mode", "full"))
        sets = {"all": list(range(bundle.X_train.shape[1])),
                "relevant": sorted(int(i) for i in bundle.relevant_features)}
        for result in artifact["results"]:
            sets.setdefault(",".join(map(str, result["support"])), result["support"])
        scores = {label: downstream(bundle, np.asarray(indices, dtype=int), seed, threads)["roc_auc"]
                  for label, indices in sets.items()}
        output[key] = dict(dataset=name, seed=seed, auc=scores,
            by_method={r["method"]: scores[",".join(map(str, r["support"]))] for r in artifact["results"]})
        target.write_text(json.dumps(output, indent=1, sort_keys=True))
        print(key, {k: round(v, 4) for k, v in output[key]["by_method"].items()},
              round(scores["all"], 4), round(scores["relevant"], 4), flush=True)


if __name__ == "__main__":
    main()
