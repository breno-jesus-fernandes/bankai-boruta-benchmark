"""Fresh process: load cached Industrial, fit once, report time and peak RSS.

Usage: python memfit.py {bankai_exact,bankai_binned,borutapy} ROUNDS THREADS SEED
Run cache_industrial.py SEED first; the arrays are read from the working directory.
"""
import os, sys, json, time, resource
import numpy as np
method, rounds, threads, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
X = np.load(f"ind{seed}_X.npy"); y = np.load(f"ind{seed}_y.npy")
base = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20
common = dict(n_estimators=100, perc=100, alpha=0.05, two_step=True, max_iter=rounds + 1, random_state=seed)
t = time.perf_counter()
if method.startswith("bankai"):
    from bankai_boruta import BankaiBoruta
    from bankai_random_forest import BankaiRandomForestClassifier
    binned = "binned" in method
    est = BankaiRandomForestClassifier(n_estimators=100, max_depth=6, max_features="sqrt", bootstrap=True, n_jobs=threads, random_state=seed,
        extra_trees=True, extra_trees_backend="binned" if binned else "exact", max_bins=63 if binned else None)
    sel = BankaiBoruta(estimator=est, **common).fit(X, y); r = sel.n_iter_; mode = sel.diagnostics_["storage_mode"]
else:
    from boruta import BorutaPy
    from sklearn.ensemble import ExtraTreesClassifier
    est = ExtraTreesClassifier(n_estimators=100, max_depth=6, max_features="sqrt", bootstrap=True, n_jobs=threads, random_state=seed)
    class C(BorutaPy):
        n = 0
        def _add_shadows_get_imps(self, *a):
            C.n += 1; return super()._add_shadows_get_imps(*a)
    sel = C(est, verbose=0, **common).fit(X, y); r = C.n; mode = "python"
dt = time.perf_counter() - t
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20
print(json.dumps(dict(method=method, ref=os.environ.get("BANKAI_BORUTA_EXACT_REFERENCE") == "1", mode=mode, seed=seed, rounds=r, seconds=round(dt, 2),
                      base_mib=round(base), peak_mib=round(peak), fit_delta_mib=round(peak - base), support=np.flatnonzero(sel.support_).tolist())))
