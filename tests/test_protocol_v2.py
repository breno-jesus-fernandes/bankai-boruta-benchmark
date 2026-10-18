import json
from pathlib import Path
import numpy as np
import pytest
from bankai_benchmark.config import COMPETITORS, PROFILES, PROTOCOL, Trial, digest
from bankai_benchmark.datasets import generate_dataset, cache_dataset, standardize, mixed_interaction
from bankai_benchmark.metrics import selection_metrics
from bankai_benchmark.orchestrator import manifest_for, ensure_manifest
from bankai_benchmark.aggregate_latex import validated_results, aggregate


@pytest.mark.parametrize('dataset', PROFILES)
def test_weights_intensities_and_mixed_metadata(dataset):
    bundle = generate_dataset(dataset, 42, 'smoke')
    m = bundle.metadata
    expected = {'industrial':[1,1,.25,.25,.02,.02], 'credito':[1]*7+[.25]*4+[.02]*3,
                'bioinformatica':[.35]*10+[1]*10, 'ciberseguranca':([1]*10+[.25]*6+[.02]*4)*3}[dataset]
    assert m['protocol'] == PROTOCOL and m['generator_version'] == '2.0.0'
    assert m['effect_weights'] == expected
    assert set().union(*map(set,m['intensity_groups'].values())) == set(bundle.relevant_features)
    selected = np.ones(bundle.X_train.shape[1], bool)
    assert set(selection_metrics(selected,bundle.relevant_features,{},intensity_groups=m['intensity_groups'])['intensity_recall'].values()) == {1.}
    if dataset == 'bioinformatica':
        assert m['interaction_type'] == 'interaction_with_marginal_effect'
        assert len(bundle.feature_subtypes['interaction_marginal_signal']) == 20


def test_mixed_effect_has_marginal_signal():
    rng=np.random.default_rng(42)
    u,v=rng.normal(size=(2,100000))
    mixed=standardize(mixed_interaction(u,v))
    assert np.corrcoef(u,mixed)[0,1] > .2
    assert abs(np.corrcoef(u,standardize(np.tanh(2*u*v)))[0,1]) < .02


def test_cache_invalidation(tmp_path,monkeypatch):
    import bankai_benchmark.datasets as module
    first=cache_dataset(tmp_path,'industrial',42,'smoke')
    monkeypatch.setattr(module,'GENERATOR_VERSION','future')
    assert cache_dataset(tmp_path,'industrial',42,'smoke') != first


def test_manifest_protocol_rejects_old(tmp_path):
    t=Trial('x','quality','smoke','industrial',COMPETITORS[0],42,1)
    manifest=manifest_for([t]);old=dict(manifest);old.pop('protocol')
    path=tmp_path/'manifest.json';path.write_text(json.dumps(old))
    with pytest.raises(ValueError,match='Incompatible'): ensure_manifest(path,manifest)


def test_historical_seven_method_manifest(tmp_path):
    from bankai_benchmark.config import HISTORICAL_COMPETITORS
    specs=[]
    for c in HISTORICAL_COMPETITORS:
        t=Trial('old','quality','smoke','industrial',c,42,1)
        specs.append(dict(experiment_id='old',suite='quality',mode='smoke',dataset='industrial',competitor=c,seed=42,threads=1,configuration_hash='historical',key=t.key))
    m=dict(source_hash='historical',package_versions={'bankai-boruta':'0.1.0a4'},trials=specs)
    m['configuration_hash']=digest(m)
    root=tmp_path/'old';root.mkdir();(root/'manifest.json').write_text(json.dumps(m))
    rows,expected,issues=validated_results(tmp_path)
    assert len(expected)==7 and len(issues)==7
    aggregate(tmp_path,tmp_path/'out',provisional=True)
    tokens=json.loads((tmp_path/'out/placeholder_replacements.json').read_text())
    assert '{{GR}}' in tokens


def test_v2_reports_exclude_greedy_and_use_new_scaling(tmp_path):
    from test_aggregation import fake_result
    from bankai_benchmark.config import atomic_json
    from bankai_benchmark.reporting_v2 import report
    roots=[]
    for suite, threads in [('quality',[16]), ('scaling',[1,2])]:
        root=tmp_path/suite;roots.append(root)
        trials=[Trial(suite,suite,'smoke','industrial',c,42,t) for c in COMPETITORS for t in threads]
        atomic_json(root/suite/'manifest.json',manifest_for(trials))
        for trial in trials: atomic_json(root/trial.key,fake_result(trial))
    report(*roots,tmp_path/'report')
    text=(tmp_path/'report/quality/wmecai_table1.tex').read_text()
    assert 'greedy' not in text.lower()
    assert '{{GR}}' not in (tmp_path/'report/quality/placeholder_replacements.json').read_text()
    assert (tmp_path/'report/scaling.svg').exists()
