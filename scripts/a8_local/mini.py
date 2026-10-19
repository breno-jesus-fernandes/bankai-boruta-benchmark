"""Round counts on the first ROWS Industrial seed-42 rows: python mini.py ROWS SEEDS METHODS."""
import sys, json, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from bankai_benchmark.datasets import generate_dataset
from bankai_boruta import BankaiBoruta
from bankai_random_forest import BankaiRandomForestClassifier
from sklearn.ensemble import ExtraTreesClassifier
from boruta import BorutaPy
ROWS = int(sys.argv[1]); SEEDS = range(int(sys.argv[2])); methods = sys.argv[3].split(",")
b = generate_dataset("industrial", 42, "full")
X = np.ascontiguousarray(b.X_train[:ROWS]); y = b.y_train[:ROWS]
class Counted(BorutaPy):
    def _add_shadows_get_imps(self, *a):
        self.calls = getattr(self, "calls", 0) + 1
        return super()._add_shadows_get_imps(*a)
def bankai_rf(seed): return BankaiRandomForestClassifier(n_estimators=100, max_depth=6, max_features="sqrt", bootstrap=True, n_jobs=4,
        random_state=seed, extra_trees=True, extra_trees_backend="exact", max_bins=None, importance_type="gain")
common = lambda s: dict(n_estimators=100, perc=100, alpha=0.05, two_step=True, max_iter=41, random_state=s)
for s in SEEDS:
    for m in methods:
        t = time.perf_counter()
        if m == "binned":
            est = BankaiRandomForestClassifier(n_estimators=100, max_depth=6, max_features="sqrt", bootstrap=True, n_jobs=4,
                random_state=s, extra_trees=True, extra_trees_backend="binned", max_bins=63, importance_type="gain")
            sel = BankaiBoruta(estimator=est, **common(s)).fit(X, y); r = sel.n_iter_
        elif m in ("native", "adapter"):
            kw = {} if m == "native" else {"importance_getter": lambda e: e.feature_importances_}
            sel = BankaiBoruta(estimator=bankai_rf(s), **kw, **common(s)).fit(X, y); r = sel.n_iter_
        else:
            est = bankai_rf(s) if m == "py_bankai" else ExtraTreesClassifier(n_estimators=100, max_depth=6, max_features="sqrt", bootstrap=True, n_jobs=4, random_state=s)
            sel = Counted(est, **common(s)).fit(X, y); r = sel.calls
        print(json.dumps(dict(seed=s, m=m, rounds=r, conf=int(sel.support_.sum()), tp=int(sel.support_[sorted(b.relevant_features)].sum()), tent=int((~sel.support_ & ~(sel.ranking_ > 2)).sum()) , t=round(time.perf_counter()-t, 1))), flush=True)
