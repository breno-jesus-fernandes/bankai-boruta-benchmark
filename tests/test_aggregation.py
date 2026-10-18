from dataclasses import asdict,replace
import csv
import json
import numpy as np
import pytest
from bankai_benchmark.config import COMPETITORS,SEEDS,Trial,atomic_json,digest
from bankai_benchmark.orchestrator import manifest_for
from bankai_benchmark.worker_single_run import base_result
from bankai_benchmark.aggregate_latex import distribution,aggregate,placeholder_values


def fake_result(t,time=10.,recall=.5):
    r=base_result(t)
    r.update(status='success',execution_metrics=dict(fit_seconds=time,peak_rss_gib=2.,delta_peak_gib=1.,completed_rounds=3,seconds_per_round=time/3),
        selection_metrics=dict(precision=.5,recall=recall,f1=.5,fdr=.5,tp=10,fp=5,fp_trap_noise=2,fp_trap_noise_rate=.1,tentative_count=3,subtype_recall={'signal':recall,'absent':None}),
        downstream_metrics=dict(roc_auc=.8,accuracy=.7,balanced_accuracy=.7,f1=.6,seconds=.2))
    return r


def test_quantile_fixture():
    assert distribution([1,2,3,4]) == dict(median=2.5,q1=1.75,q3=3.25,iqr=1.5)
    assert distribution([])['median'] is None


def test_every_placeholder_and_paired_ratios():
    from pathlib import Path
    import bankai_benchmark.aggregate_latex as module
    mapping=json.loads(Path(module.__file__).with_name('config-paper.json').read_text())
    rows=[]
    for c in COMPETITORS:
        for i,s in enumerate(SEEDS):
            t=Trial('test-quality','quality','full','industrial',c,s,16)
            rows.append(fake_result(t,time=(i+1)*(2 if c == 'bankai_classic_adapter' else 1),recall=.8 if c == 'bankai_classic_native' else .7))
    tokens,complete=placeholder_values(rows,mapping)
    assert complete
    assert set(tokens) == {'CR','CA','BP','ET','mCR','mCA','mBP','mET','rCR','rCA','rBP','rET','infoC','ruidoC','razao','delta'}
    assert tokens['razao'] == 2 and tokens['delta'] == pytest.approx(10)
    assert tokens['CR'] == 3 and tokens['CA'] == 6 and tokens['ET'] == 3
    assert all(tokens[k] == 2 for k in ('mCR','mCA','mBP','mET'))
    assert tokens['infoC'] == 10 and tokens['ruidoC'] == 5
    assert not placeholder_values(rows[1:],mapping)[1]


def test_manifest_reports_and_failures(tmp_path):
    trials=tuple(Trial('test-scaling','scaling','full','industrial','bankai_classic_native',s,t) for t in [1,2] for s in [42,43])
    root=tmp_path/'results';atomic_json(root/'test-scaling/manifest.json',manifest_for(trials))
    times=[2,100,1,100]
    for t,time in zip(trials,times):atomic_json(root/t.key,fake_result(t,time))
    output=tmp_path/'report';assert not aggregate(root,output,provisional=True)
    rows=list(csv.DictReader((output/'thread_scaling.csv').open()))
    assert float(rows[1]['speedup_median']) == 1.5
    assert float(rows[1]['efficiency_median']) == .75
    report=json.loads((output/'completeness.json').read_text());assert report['successful'] == 4
    result=json.loads((root/trials[0].key).read_text());result.update(status='timeout',execution_metrics=None)
    atomic_json(root/trials[0].key,result)
    aggregate(root,output)
    rows=list(csv.DictReader((output/'summary_by_dataset.csv').open()))
    assert float(rows[0]['fit_seconds_median']) == 100 and rows[0]['failures'] == '1'
    tokens=json.loads((output/'placeholder_replacements.json').read_text())
    assert all(v is None for v in tokens.values())
    assert 'PROVISIONAL' in (output/'wmecai_placeholders.tex').read_text()
    result['configuration_hash']='bad';atomic_json(root/trials[0].key,result)
    with pytest.raises(ValueError,match='Manifest mismatch'):aggregate(root,output)


def test_missing_experiment(tmp_path):
    with pytest.raises(ValueError,match='No manifests'):aggregate(tmp_path,tmp_path/'report')
