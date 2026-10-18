import numpy as np
import pytest
from bankai_benchmark.config import PROFILES,RELEVANT_COUNTS,profile
from bankai_benchmark.datasets import allocate,cache_dataset,generate_dataset,load_dataset

@pytest.mark.parametrize('dataset',list(PROFILES))
def test_dataset_contract(dataset,tmp_path):
    a=generate_dataset(dataset,42,'smoke');b=generate_dataset(dataset,42,'smoke');cfg=profile(dataset,'smoke')
    assert a.X_train.shape == (400,cfg.p) and a.X_test.shape == (100,cfg.p)
    assert len(a.relevant_features) == RELEVANT_COUNTS[dataset]
    for X in [a.X_train,a.X_test]:assert X.dtype == np.float32 and X.flags.c_contiguous
    assert a.y_train.dtype == np.int32 and a.y_test.dtype == np.int32
    np.testing.assert_array_equal(a.X_train,b.X_train);np.testing.assert_array_equal(a.y_train,b.y_train)
    assert a.metadata == b.metadata and a.y_train.sum() == round(400*cfg.prevalence)
    assert abs(a.y_test.mean()-cfg.prevalence) <= 1/100
    calibration=a.metadata['calibration']
    assert calibration['signal_variance'] == pytest.approx(1)
    assert calibration['noise_variance'] == pytest.approx(1)
    assert calibration['realized_snr'] == pytest.approx(cfg.snr)
    np.testing.assert_allclose(calibration['term_means'],0,atol=1e-12)
    np.testing.assert_allclose(calibration['term_variances'],1,atol=1e-12)
    assert sorted(i for v in a.feature_subtypes.values() for i in v) == list(range(cfg.p))
    relevant=[v for k,v in a.feature_subtypes.items() if 'signal' in k or k == 'redundant']
    assert sorted(i for v in relevant for i in v) == a.relevant_features.tolist()
    inverse=np.argsort(a.metadata['column_permutation'])
    assert np.sort(inverse[:RELEVANT_COUNTS[dataset]]).tolist() == a.relevant_features.tolist()
    if dataset == 'credito':
        for i in a.feature_subtypes['categorical_signal']:
            np.testing.assert_array_equal(a.X_train[:,i],a.X_train[:,i].astype(int))
            assert a.X_train[:,i].min() >= 0 and a.X_train[:,i].max() < 50
    directory=cache_dataset(tmp_path,dataset,42,'smoke')
    np.testing.assert_array_equal(load_dataset(directory).X_train,a.X_train)
    assert directory == cache_dataset(tmp_path,dataset,42,'smoke')
    assert not np.array_equal(a.X_train,generate_dataset(dataset,43,'smoke').X_train)

def test_full_geometry_without_allocations():
    assert [(p.n,p.p,p.trees,p.depth,p.max_iter) for p in PROFILES.values()] == [(200000,500,100,6,120),(300000,300,100,6,120),(50000,2000,150,8,120),(400000,150,100,6,120)]
    for name in PROFILES:
        for mode in ['full','smoke','smoke-matrix']:assert profile(name,mode).p >= RELEVANT_COUNTS[name]
    assert allocate(5,[1,1,1]).tolist() == [2,2,1]
    assert allocate(280,[40,240]).tolist() == [40,240]
