"""Reproduce README speedups from the completed quality campaign (standard library)."""
import json
import math
from pathlib import Path

ARCHIVE = Path(__file__).resolve().parents[1] / 'verification/campaign-20261017'
DATASETS = ('industrial', 'credito', 'bioinformatica', 'ciberseguranca')
BASELINE = 'bankai_classic_native'
REFERENCES = ('borutapy_lightgbm_rf', 'borutapy_sklearn_et')


def summarize(raw):
    observations = {}
    for path in sorted(raw.glob('*/*.json')):
        row = json.loads(path.read_text())
        if row['competitor'] not in (BASELINE, *REFERENCES):
            continue
        key = (row['dataset'], row['competitor'], row['seed'])
        if key in observations:
            raise ValueError(f'Duplicate observation: {key}')
        if row['status'] != 'success' or row['threads'] != 16 or row['mode'] != 'full' or row['suite'] != 'quality':
            raise ValueError(f'Invalid quality observation: {path}')
        value = row['execution_metrics']['fit_seconds']
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f'Invalid fit time: {path}')
        observations[key] = value
    result = {}
    for reference in REFERENCES:
        ratios = []
        profiles = {}
        for dataset in DATASETS:
            paired = [observations[dataset, reference, seed] / observations[dataset, BASELINE, seed]
                      for seed in range(42, 47)]
            profiles[dataset] = math.exp(sum(map(math.log, paired)) / len(paired))
            ratios.extend(paired)
        result[reference] = {'paired_observations': len(ratios),
                             'geometric_mean_speedup': math.exp(sum(map(math.log, ratios)) / len(ratios)),
                             'by_dataset': profiles}
    return {'baseline': BASELINE, 'threads': 16, 'statistic': 'exp(mean(log(reference_seconds / baseline_seconds)))',
            'comparisons': result}


if __name__ == '__main__':
    print(json.dumps(summarize(ARCHIVE / 'quality/input/pilot-20261017-quality/raw'), indent=2))
