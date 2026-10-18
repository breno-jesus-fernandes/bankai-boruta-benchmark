"""Deterministic joint synthetic calibration; no model fits on test rows."""
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import hashlib
import numpy as np
from scipy.special import expit
from .config import GENERATOR_VERSION, PROTOCOL, EFFECT_WEIGHTS, MARGINAL_COEFFICIENT, profile, digest, atomic_json


@dataclass
class DatasetBundle:
    X_train: np.ndarray
    X_test: np.ndarray
    y_train: np.ndarray
    y_test: np.ndarray
    relevant_features: np.ndarray
    feature_subtypes: dict
    metadata: dict


def generator_hash():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def standardize(x):
    x = np.asarray(x, dtype=np.float64)
    return (x-x.mean(axis=0)) / np.maximum(x.std(axis=0), 1e-12)


def mixed_interaction(u, v):
    return np.tanh(2*u*v) + MARGINAL_COEFFICIENT*(u+v)/np.sqrt(2)


def allocate(total, weights):
    raw = np.asarray(weights, float) / sum(weights) * total
    counts = np.floor(raw).astype(int)
    counts[np.argsort(-(raw-counts), kind="stable")[:total-counts.sum()]] += 1
    return counts


def generate_dataset(dataset_id, seed, mode):
    cfg = profile(dataset_id, mode)
    if dataset_id not in EFFECT_WEIGHTS: raise ValueError(dataset_id)
    n = cfg.n + round(cfg.n/4)
    rng, weights, noise, perm_rng, split = [np.random.default_rng(s) for s in np.random.SeedSequence(seed).spawn(5)]
    columns, subtypes, relevant, effects, effect_weights = [], {}, [], [], []

    def add(name, values, causal=False):
        values = np.asarray(values)
        if values.ndim == 1:
            values = values[:, None]
        start = len(columns)
        columns.extend(values.T)
        subtypes.setdefault(name, []).extend(range(start, len(columns)))
        if causal:
            relevant.extend(range(start, len(columns)))

    if dataset_id == "industrial":
        roots = rng.normal(size=(n, 6)); add("signal", roots, True)
        add("redundant", .95*roots + np.sqrt(1-.95**2)*rng.normal(size=roots.shape), True)
        effects = [roots[:, i] for i in range(3)] + [roots[:, i]**2 for i in (3, 4)] + [roots[:, 5]*roots[:, 0]]
        effect_weights = EFFECT_WEIGHTS[dataset_id]
        counts = allocate(cfg.p-12, [1, 1, 1])
        latent = rng.normal(size=(n, max(1, int(np.ceil(counts[0]/10)))))
        block = np.empty((n, counts[0]))
        for j in range(counts[0]):
            block[:, j] = .8*latent[:, j//10] + .6*rng.normal(size=n)
        add("correlated_noise", block)
        add("trap_noise", rng.uniform(size=(n, counts[1])))
        add("gaussian_noise", rng.normal(size=(n, counts[2])))
    elif dataset_id == "credito":
        roots = rng.lognormal(size=(n, 6)); add("signal", roots, True)
        effects = [np.log1p(roots[:, i]) for i in range(6)]
        cards = [2, 3, 4, 5, 8, 10, 20, 50]
        for card in cards:
            x = rng.integers(card, size=n); add("categorical_signal", x, True)
            effects.append(weights.normal(size=card)[x])
        effect_weights = EFFECT_WEIGHTS[dataset_id]
        add("redundant", roots+.1*rng.normal(size=roots.shape), True)
        counts = allocate(cfg.p-20, [40, 240])
        for j in range(counts[0]):
            add("trap_noise", rng.integers(cards[j % 8], size=n))
        add("gaussian_noise", rng.normal(size=(n, counts[1])))
    elif dataset_id == "bioinformatica":
        correlation = .8**np.abs(np.arange(10)[:, None]-np.arange(10))
        block = rng.normal(size=(n, 10)) @ np.linalg.cholesky(correlation).T
        add("correlated_signal", block, True)
        uv = rng.normal(size=(n, 20)); add("interaction_marginal_signal", uv, True)
        effects = [block[:, i] for i in range(10)] + [mixed_interaction(uv[:, 2*i], uv[:, 2*i+1]) for i in range(10)]
        effect_weights = EFFECT_WEIGHTS[dataset_id]
        counts = allocate(cfg.p-30, [1, 1])
        add("trap_noise", rng.uniform(size=(n, counts[0])))
        add("gaussian_noise", rng.normal(size=(n, counts[1])))
    else:
        step = rng.normal(size=(n, 20)); periodic = rng.uniform(-np.pi, np.pi, size=(n, 20))
        sparse = rng.binomial(1, .05, size=(n, 20))*rng.exponential(size=(n, 20))
        add("step_signal", step, True); add("periodic_signal", periodic, True); add("sparse_signal", sparse, True)
        effects = [*(step > 0).T, *np.sin(periodic).T, *sparse.T]
        effect_weights = EFFECT_WEIGHTS[dataset_id]
        counts = allocate(cfg.p-60, [1, 1])
        add("trap_noise", rng.uniform(size=(n, counts[0])))
        add("gaussian_noise", rng.normal(size=(n, counts[1])))
    # Features can participate in multiple intensities (Industrial x0 also interacts).
    term_features = ([[i] for i in range(3)] + [[3], [4], [5, 0]] if dataset_id == "industrial" else
                     [[i] for i in range(14)] if dataset_id == "credito" else
                     [[i] for i in range(10)] + [[10+2*i, 11+2*i] for i in range(10)] if dataset_id == "bioinformatica" else
                     [[i] for i in range(60)])
    intensity = {}
    for weight, indices in zip(effect_weights, term_features):
        label = "strong" if weight == 1 else "weak" if weight == .02 else "medium"
        group = intensity.setdefault(label, set())
        group.update(indices)
        if dataset_id == "industrial": group.update(i+6 for i in indices)
        if dataset_id == "credito": group.update(i+14 for i in indices if i < 6)
    terms = np.column_stack([standardize(term) for term in effects])
    signal = standardize(terms @ np.asarray(effect_weights or [1.]*len(effects)))
    logistic_noise = standardize(noise.logistic(size=n))
    logit = np.sqrt(cfg.snr)*signal + logistic_noise
    positives = round(n*cfg.prevalence)
    y = np.zeros(n, dtype=np.int32)
    y[np.argsort(expit(logit), kind="stable")[-positives:]] = 1
    permutation = perm_rng.permutation(cfg.p); inverse = np.argsort(permutation)
    X = np.ascontiguousarray(np.asarray(columns, dtype=np.float32).T[:, permutation])
    train_positive = round(cfg.n*cfg.prevalence)
    train, test = [], []
    for cls, count in ((0, cfg.n-train_positive), (1, train_positive)):
        indices = split.permutation(np.flatnonzero(y == cls))
        train.extend(indices[:count]); test.extend(indices[count:])
    train = split.permutation(train); test = split.permutation(test)
    metadata = dict(protocol=PROTOCOL, effect_weights=effect_weights, term_features=term_features,
        intensity_groups={k: sorted(inverse[list(v)].tolist()) for k, v in intensity.items()},
        interaction_type="interaction_with_marginal_effect" if dataset_id == "bioinformatica" else None, generator_version=GENERATOR_VERSION, generator_hash=generator_hash(), configuration_hash=digest(dict(profile=asdict(cfg), weights=effect_weights, marginal_coefficient=MARGINAL_COEFFICIENT, protocol=PROTOCOL)), dataset=dataset_id,
        seed=seed, mode=mode, dimensions=[cfg.n, cfg.p], class_counts_train=np.bincount(y[train], minlength=2).tolist(),
        class_counts_test=np.bincount(y[test], minlength=2).tolist(), column_permutation=permutation.tolist(),
        calibration=dict(scope="joint_train_test_synthetic", signal_variance=float(signal.var()), noise_variance=float(logistic_noise.var()),
                         realized_snr=float((np.sqrt(cfg.snr)*signal).var()/logistic_noise.var()), snr=cfg.snr,
                         term_means=terms.mean(axis=0).tolist(), term_variances=terms.var(axis=0).tolist()))
    return DatasetBundle(np.ascontiguousarray(X[train]), np.ascontiguousarray(X[test]), y[train], y[test],
                         np.sort(inverse[relevant]), {k: sorted(inverse[v].tolist()) for k, v in subtypes.items()}, metadata)


def cache_dataset(root, dataset, seed, mode):
    key = digest(dict(profile=asdict(profile(dataset, mode)), seed=seed, generator_version=GENERATOR_VERSION, generator_hash=generator_hash(), effect_weights=EFFECT_WEIGHTS[dataset], marginal_coefficient=MARGINAL_COEFFICIENT))
    directory = Path(root)/key
    if not (directory/"metadata.json").exists():
        bundle = generate_dataset(dataset, seed, mode)
        directory.mkdir(parents=True, exist_ok=True)
        for name in ("X_train", "X_test", "y_train", "y_test", "relevant_features"):
            np.save(directory/f"{name}.npy", getattr(bundle, name), allow_pickle=False)
        atomic_json(directory/"metadata.json", dict(metadata=bundle.metadata, feature_subtypes=bundle.feature_subtypes))
    return directory


def load_dataset(directory):
    directory = Path(directory)
    info = json.loads((directory/"metadata.json").read_text())
    arrays = {name: np.load(directory/f"{name}.npy", mmap_mode="r", allow_pickle=False)
              for name in ("X_train", "X_test", "y_train", "y_test", "relevant_features")}
    return DatasetBundle(**arrays, **info)
