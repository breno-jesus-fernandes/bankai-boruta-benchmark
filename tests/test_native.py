import numpy as np
import pytest
from bankai_boruta import BankaiBoruta
from bankai_random_forest import BankaiRandomForestClassifier

@pytest.mark.parametrize('threads', [1, 4])
@pytest.mark.parametrize('features', ['sqrt', .15, 3, None, 'log2'])
def test_native_adapter_parity(threads, features):
    X = np.random.default_rng(100).normal(size=(96,20)); y = (X[:,0]+X[:,1]>0).astype(int)
    base = BankaiRandomForestClassifier(n_estimators=5,max_depth=3,max_bins=63,max_features=features,n_jobs=threads,extra_trees=True,extra_trees_backend='binned')
    kwargs = dict(n_estimators=5,random_state=42,max_iter=4,greedy=False,store_history=True)
    native = BankaiBoruta(base,**kwargs).fit(X,y)
    adapter = BankaiBoruta(base,importance_getter='feature_importances_',**kwargs).fit(X,y)
    assert native.diagnostics_['path'] == 'rust' and adapter.diagnostics_['path'] == 'python'
    assert native.diagnostics_['copied_bytes'] == 0 and adapter.diagnostics_['copied_bytes'] > 0
    np.testing.assert_allclose(native.importance_history_,adapter.importance_history_,atol=1e-14,equal_nan=True)
    np.testing.assert_array_equal(native.support_,adapter.support_)
    assert native.n_iter_ == adapter.n_iter_


def test_fractional_sampling_parity_after_classic_rejections():
    X = np.random.default_rng(8).normal(size=(160, 20))
    y = (X[:, 0] > 0).astype(int)
    base = BankaiRandomForestClassifier(n_estimators=8, max_depth=3, max_bins=63,
        max_features=.15, n_jobs=2, extra_trees=True, extra_trees_backend='binned')
    kwargs = dict(n_estimators=8, random_state=42, max_iter=20, store_history=True)
    native = BankaiBoruta(base, **kwargs).fit(X, y)
    adapter = BankaiBoruta(base, importance_getter='feature_importances_', **kwargs).fit(X, y)
    # Rejected features disappear, so fractional counts must follow changing widths.
    assert np.isnan(native.importance_history_[-1]).sum() > 0
    np.testing.assert_allclose(native.importance_history_, adapter.importance_history_,
                               atol=1e-14, equal_nan=True)
    np.testing.assert_array_equal(native.support_, adapter.support_)
