from dataclasses import replace
from math import ceil,log2
import json
import numpy as np
import pytest
from sklearn.base import clone
from bankai_benchmark.competitors import estimator,fit_select,PythonGreedy
from bankai_benchmark.config import COMPETITORS,Trial
from bankai_benchmark.datasets import generate_dataset
from bankai_benchmark.metrics import downstream,selection_metrics

def trial(competitor='bankai_classic_native'):return Trial('test-quality','quality','smoke','industrial',competitor,42,1)

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
    if competitor.endswith('native'):assert result.diagnostics['path'] == 'rust'

def test_lightgbm_width_and_cloning():
    model=clone(estimator(trial('borutapy_lightgbm_rf'),'lightgbm'))
    X=np.random.default_rng(4).normal(size=(40,80));y=np.arange(40)%2
    model.fit(X,y);assert model.colsample_bytree == 8/80
    model=clone(model)
    model.fit(X[:,:20],y);assert model.colsample_bytree == 4/20
    model=estimator(replace(trial(),dataset='bioinformatica'),'lightgbm')
    model.fit(X,y);assert model.colsample_bytree == .15

def test_greedy_strict_hit_once_full_set():
    class Controlled:
        calls=0
        def set_params(self,**kwargs):return self
        def fit(self,X,y):
            self.calls+=1;assert X.shape[1] == 6
            self.feature_importances_=np.array([2 if self.calls == 1 else 0,1,0,1,1,1])
    model=Controlled();result=PythonGreedy(model,.05,42).fit(np.zeros((10,3)),np.arange(10)%2)
    assert model.calls == result.n_iter_ == ceil(log2(3/.05))
    assert result.support_.tolist() == [True,False,False]
