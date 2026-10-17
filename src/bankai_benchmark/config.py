from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path

SCHEMA_VERSION = 1
GENERATOR_VERSION = "1.0.0"
SEEDS = (42, 43, 44, 45, 46)
COMPETITORS = ("bankai_classic_native", "bankai_classic_adapter", "bankai_greedy_native",
               "borutapy_lightgbm_rf", "borutapy_sklearn_et", "greedy_borutapy_bankai", "greedy_borutapy_lightgbm")
DOWNSTREAM = dict(n_estimators=200, max_features="sqrt", class_weight="balanced")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def dependency_hash():
    import importlib.metadata
    return digest({name: importlib.metadata.version(name) for name in
                   ("bankai-boruta", "bankai-random-forest", "Boruta", "lightgbm", "numpy", "scipy", "scikit-learn")})


def source_hash():
    return digest({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob("*.py"))})


@dataclass(frozen=True)
class Profile:
    dataset: str
    n: int
    p: int
    trees: int
    depth: int
    bins: int
    max_features: str | float
    max_iter: int
    prevalence: float
    snr: float
    alpha: float = .05


PROFILES = {
    "industrial": Profile("industrial", 100000, 500, 100, 6, 63, "sqrt", 50, .5, 2.),
    "credito": Profile("credito", 150000, 300, 100, 6, 63, "sqrt", 50, .2, 2.),
    "bioinformatica": Profile("bioinformatica", 25000, 2000, 150, 8, 63, .15, 60, .5, 1.),
    "ciberseguranca": Profile("ciberseguranca", 200000, 150, 100, 6, 63, "sqrt", 40, .1, 2.),
}
RELEVANT_COUNTS = dict(industrial=12, credito=20, bioinformatica=30, ciberseguranca=60)


def profile(dataset, mode):
    cfg = PROFILES[dataset]
    if mode == "smoke":
        return replace(cfg, n=400, p=max(40, RELEVANT_COUNTS[dataset]), trees=8, depth=3, max_iter=4)
    if mode == "smoke-matrix":
        return replace(cfg, n=int(cfg.n*.05), p=max(RELEVANT_COUNTS[dataset], round(cfg.p*.3)), max_iter=10)
    if mode != "full":
        raise ValueError(mode)
    return cfg


@dataclass(frozen=True)
class Trial:
    experiment_id: str
    suite: str
    mode: str
    dataset: str
    competitor: str
    seed: int
    threads: int
    warmup: bool = False

    @property
    def configuration_hash(self):
        return digest(dict(profile=asdict(profile(self.dataset, self.mode)), generator=GENERATOR_VERSION,
                           source_hash=source_hash(), dependencies=dependency_hash(), downstream=DOWNSTREAM, competitor=self.competitor, threads=self.threads))

    @property
    def trial_id(self):
        return f"{self.competitor}_s{self.seed}_t{self.threads}"

    @property
    def key(self):
        return f"{self.experiment_id}/raw/{self.dataset}/{self.trial_id}.json"


def trial_grid(experiment_id, mode, suite, dataset=None):
    datasets = [dataset] if dataset else (["industrial"] if mode == "smoke" or suite == "scaling" else list(PROFILES))
    seeds = (42,) if mode == "smoke" else ((42, 43) if mode == "smoke-matrix" else SEEDS)
    threads = (1,) if mode == "smoke" else ((1, 4) if mode == "smoke-matrix" else ((1, 2, 4, 8, 16) if suite == "scaling" else (16,)))
    return tuple(Trial(experiment_id, suite, mode, d, c, s, t) for d in datasets for c in COMPETITORS for t in threads for s in seeds)


def atomic_json(path, data):
    import os
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    with temporary.open("w") as handle:
        json.dump(data, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def json_parameters(parameters):
    """Encode BorutaPy's RandomState without memory addresses or unsafe objects."""
    import numpy as np
    out = {}
    for key, value in parameters.items():
        if isinstance(value, np.random.RandomState):
            state = value.get_state()
            value = dict(type="RandomState", state_hash=digest([state[0], state[1].tolist(), *state[2:]]))
        elif isinstance(value, np.generic):
            value = value.item()
        elif isinstance(value, np.ndarray):
            value = value.tolist()
        out[key] = value
    return out
