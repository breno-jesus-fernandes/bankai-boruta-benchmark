"""Reports for v2; scaling uses its own one-core baseline and no quality reuse."""
import csv
import json
from pathlib import Path
from .aggregate_latex import aggregate, validated_results, write_csv
from .config import COMPETITORS, PROTOCOL, digest


def report(quality_root, scaling_root, output):
    output = Path(output)
    fingerprints = set()
    for root in (quality_root, scaling_root):
        manifests = [json.loads(p.read_text()) for p in Path(root).rglob('manifest.json')]
        if not manifests or any(m.get('protocol') != PROTOCOL for m in manifests):
            raise ValueError('v2 reporting requires exclusively compatible v2 manifests')
        fingerprints.update(digest({key: m.get(key) for key in ('protocol','source_hash','package_versions','machine')}) for m in manifests)
    if len(fingerprints) != 1:
        raise ValueError('Quality and scaling source/dependencies/machine differ')
    quality, _, _ = validated_results(quality_root)
    scaling, _, _ = validated_results(scaling_root)
    if len({r['provenance']['source_hash'] for r in quality+scaling if r.get('provenance')}) > 1:
        raise ValueError('Quality and scaling implementations differ')
    aggregate(quality_root, output/'quality', provisional=True)
    aggregate(scaling_root, output/'scaling', provisional=True)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    labels = {'bankai_native_extra_tree': 'Bankai native ExtraTrees',
              'borutapy_lightgbm_rf': 'BorutaPy LightGBM RF',
              'borutapy_sklearn_et': 'BorutaPy ExtraTrees'}
    rows = list(csv.DictReader((output/'quality/summary_by_dataset.csv').open()))
    for metric in ('fit_seconds', 'peak_rss_gib', 'recall'):
        fig, axes = plt.subplots(2, 2, figsize=(11, 7), layout='constrained')
        for ax, dataset in zip(axes.flat, ('industrial','credito','bioinformatica','ciberseguranca')):
            cells = {r['competitor']: r for r in rows if r['dataset'] == dataset}
            values = [float(cells[m][metric+'_median']) if cells.get(m, {}).get(metric+'_median') else float('nan') for m in COMPETITORS]
            ax.barh([labels[m] for m in COMPETITORS], values)
            ax.set_title(dataset); ax.set_xlabel(metric)
        fig.savefig(output/(metric+'.svg')); plt.close(fig)
    rows = list(csv.DictReader((output/'scaling/thread_scaling.csv').open()))
    fig, ax = plt.subplots(layout='constrained')
    for method in COMPETITORS:
        cells = sorted([r for r in rows if r['competitor'] == method], key=lambda r: int(r['threads']))
        ax.plot([int(r['threads']) for r in cells], [float(r['speedup_median']) if r['speedup_median'] else float('nan') for r in cells], marker='o', label=labels[method])
    ax.set(xlabel='Physical cores', ylabel='Paired speedup relative to one core', xticks=[1,2,4,8,16]); ax.legend()
    fig.savefig(output/'scaling.svg'); plt.close(fig)
