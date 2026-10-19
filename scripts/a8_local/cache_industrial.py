"""Write ind{SEED}_X.npy and ind{SEED}_y.npy (Industrial full training split)."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from bankai_benchmark.datasets import generate_dataset

for seed in map(int, sys.argv[1:]):
    bundle = generate_dataset("industrial", seed, "full")
    np.save(f"ind{seed}_X.npy", np.ascontiguousarray(bundle.X_train))
    np.save(f"ind{seed}_y.npy", bundle.y_train)
