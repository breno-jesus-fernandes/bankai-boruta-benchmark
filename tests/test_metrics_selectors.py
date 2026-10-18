from dataclasses import replace
from math import ceil,log2
import json
import numpy as np
import pytest
from sklearn.base import clone
from bankai_benchmark.competitors import estimator,fit_select,PreparedSelector
from bankai_benchmark.config import COMPETITORS,Trial
from bankai_benchmark.datasets import generate_dataset
from bankai_benchmark.metrics import downstream,selection_metrics

def trial(competitor='bankai_native_extra_tree'):return Trial('test-quality','quality','smoke','industrial',competitor,42,1)

def test_hand_metrics():
    m=selection_metrics(np.array([1,0,1,0],bool),[0,1],{'signal':[0,1],'trap_noise':[2],'absent':[]})
    assert [m[k] for k in ['tp','fp','fn','tn']] == [1,1,1,1]
    assert [m[k] for k in ['precision','recall','f1','fdr']] == [.5]*4
    assert m['fp_trap_noise'] == m['fp_trap_noise_rate'] == 1 and m['subtype_recall']['absent'] is None
    m=selection_metrics(np.zeros(4,bool),[0,1],{})
    assert [m[k] for k in ['precision','recall','f1','fdr']] == [0]*4

def test_empty_downstream():
    result=downstream(generate_dataset('industrial',42,'smoke'),[],42,1)
    assert result['roc_auc'] == .5 and result['selected_count'] == 0

@pytest.mark.parametrize('competitor',COMPETITORS)
def test_selectors(competitor):
    bundle=generate_dataset('industrial',42,'smoke')
    result=fit_select(bundle.X_train,bundle.y_train,trial(competitor))
    assert result.confirmed.shape == (40,) and result.confirmed.dtype == bool
    assert result.effective_parameters['n_estimators'] == 8
    assert result.rounds == (ceil(log2(40/.05)) if 'greedy' in competitor else 3)
    json.dumps(result.effective_parameters,allow_nan=False)
    if competitor == 'bankai_native_extra_tree':assert result.diagnostics['path'] == 'rust'

def test_lightgbm_width_and_cloning():
    model=clone(estimator(trial('borutapy_lightgbm_rf'),'lightgbm'))
    X=np.random.default_rng(4).normal(size=(40,80));y=np.arange(40)%2
    model.fit(X,y);assert model.colsample_bytree == 8/80
    model=clone(model)
    model.fit(X[:,:20],y);assert model.colsample_bytree == 4/20
    model=estimator(replace(trial(),dataset='bioinformatica'),'lightgbm')
    model.fit(X,y);assert model.colsample_bytree == .15

def test_extra_trees_bootstrap_and_current_methods():
    assert COMPETITORS == ('bankai_native_extra_tree','borutapy_lightgbm_rf','borutapy_sklearn_et')
    assert estimator(trial('borutapy_sklearn_et'),'et').bootstrap is True

@pytest.mark.parametrize('competitor',COMPETITORS)
def test_both_selectors_use_the_same_early_stopping_policy(competitor):
    selector=PreparedSelector(trial(competitor)).selector
    assert selector.early_stopping is True
    assert selector.n_iter_no_change == 100

def test_full_profiles_allow_patience_100_to_stop_before_the_iteration_cap():
    from bankai_benchmark.config import PROFILES
    assert all(cfg.max_iter == 120 for cfg in PROFILES.values())
