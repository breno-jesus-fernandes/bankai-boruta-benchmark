"""Matched budgets with explicit backend-specific ensemble semantics."""
from dataclasses import dataclass
from math import ceil, log2, sqrt
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from bankai_random_forest import BankaiRandomForestClassifier
from bankai_boruta import BankaiBoruta
from boruta import BorutaPy
from lightgbm import LGBMClassifier
from .config import COMPETITORS, profile, json_parameters


class WidthAwareLGBM(LGBMClassifier):
    """Clonable LGBM estimator; update sampling against actual shadow width."""
    def fit(self, X, y, **kwargs):
        policy = getattr(self, "_sampling_policy", self.colsample_bytree)
        self._sampling_policy = policy
        ratio = max(1, int(sqrt(X.shape[1])))/X.shape[1] if policy == 1.0 else float(policy)
        self.set_params(colsample_bytree=ratio)
        kwargs["categorical_feature"] = []
        return super().fit(X, y, **kwargs)


def estimator(trial, backend):
    cfg = profile(trial.dataset, trial.mode)
    common = dict(n_estimators=cfg.trees, max_depth=cfg.depth, n_jobs=trial.threads, random_state=trial.seed)
    if backend == "bankai":
        return BankaiRandomForestClassifier(**common, max_features=cfg.max_features, max_bins=cfg.bins,
                   extra_trees=True, extra_trees_backend="binned", importance_type="gain", bootstrap=True)
    if backend == "et":
        return ExtraTreesClassifier(**common, max_features=cfg.max_features, bootstrap=False)
    return WidthAwareLGBM(**common, boosting_type="rf", num_leaves=2**cfg.depth, max_bin=cfg.bins,
                         subsample=.8, subsample_freq=1, colsample_bytree=1.0 if cfg.max_features == "sqrt" else cfg.max_features,
                         importance_type="gain", verbosity=-1, deterministic=True, force_col_wise=True,
                         min_child_samples=2, reg_alpha=0., reg_lambda=0.)


class PythonGreedy:
    """Suite implementation: independent shadows, full set, strict hits, fixed K."""
    def __init__(self, estimator, alpha, seed):
        self.estimator = estimator
        self.alpha, self.seed = alpha, seed

    def fit(self, X, y):
        rng = np.random.RandomState(self.seed)
        p = X.shape[1]
        self.n_iter_ = ceil(log2(p/self.alpha))
        self.support_ = np.zeros(p, bool)
        self.support_weak_ = np.zeros(p, bool)
        for _ in range(self.n_iter_):
            shadows = np.column_stack([rng.permutation(X[:, i]) for i in range(p)])
            augmented = np.column_stack((X, shadows))
            self.estimator.set_params(random_state=int(rng.randint(2**31-1)))
            self.estimator.fit(augmented, y)
            scores = self.estimator.feature_importances_
            self.support_ |= scores[:p] > np.max(scores[p:])
        return self


@dataclass
class Selection:
    confirmed: np.ndarray
    tentative: np.ndarray
    rounds: int
    diagnostics: dict
    effective_parameters: dict


class PreparedSelector:
    def __init__(self, trial):
        self.trial = trial
        if trial.competitor not in COMPETITORS:
            raise ValueError(trial.competitor)
        cfg = profile(trial.dataset, trial.mode)
        name = trial.competitor
        backend = "lightgbm" if "lightgbm" in name else ("et" if name == "borutapy_sklearn_et" else "bankai")
        model = estimator(trial, backend)
        common = dict(n_estimators=cfg.trees, perc=100, alpha=cfg.alpha, two_step=True,
                      max_iter=cfg.max_iter, random_state=trial.seed, early_stopping=False)
        if name.startswith("greedy_borutapy"):
            self.selector = PythonGreedy(model, cfg.alpha, trial.seed)
        elif name.startswith("bankai"):
            self.selector = BankaiBoruta(model, **common, greedy="greedy" in name,
                               importance_getter="feature_importances_" if name.endswith("adapter") else "auto")
        else:
            self.selector = BorutaPy(model, **common)

    def fit(self, X, y):
        self.selector.fit(X, y)
        return self

    def result(self):
        name = self.trial.competitor
        selector = self.selector
        diagnostics = getattr(selector, "diagnostics_", {"path": "python"})
        if name.startswith("bankai"):
            expected = "python" if name.endswith("adapter") else "rust"
            if diagnostics["path"] != expected:
                raise RuntimeError(f"Required {expected} path, got {diagnostics}")
        rounds = len(selector.importance_history_)-1 if isinstance(selector, BorutaPy) else selector.n_iter_
        fitted = getattr(selector, "estimator_", selector.estimator)
        return Selection(selector.support_, selector.support_weak_, rounds, diagnostics, json_parameters(fitted.get_params()))


def fit_select(X, y, trial):
    return PreparedSelector(trial).fit(X, y).result()


REGISTRY = dict.fromkeys(COMPETITORS, fit_select)
