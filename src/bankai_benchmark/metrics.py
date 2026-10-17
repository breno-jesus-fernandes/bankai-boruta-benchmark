import time
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, roc_auc_score
from .config import DOWNSTREAM


def selection_metrics(selected, relevant, subtypes, tentative=None):
    chosen = set(np.flatnonzero(selected).tolist()); truth = set(np.asarray(relevant).tolist())
    tp, fp, fn = len(chosen & truth), len(chosen-truth), len(truth-chosen)
    precision = tp/len(chosen) if chosen else 0.
    recall = tp/len(truth) if truth else 0.
    traps = set(subtypes.get("trap_noise", []))
    return dict(tp=tp, fp=fp, fn=fn, tn=len(selected)-tp-fp-fn, selected_count=len(chosen),
        tentative_count=int(np.sum(tentative)) if tentative is not None else 0,
        precision=precision, recall=recall, f1=2*precision*recall/(precision+recall) if precision+recall else 0.,
        fdr=fp/len(chosen) if chosen else 0., fp_trap_noise=len(chosen & traps),
        fp_trap_noise_rate=len(chosen & traps)/len(traps) if traps else None,
        subtype_recall={name: len(chosen & set(indices) & truth)/len(set(indices) & truth)
                        if set(indices) & truth else None for name, indices in subtypes.items()})


def downstream(bundle, indices, seed, threads):
    started = time.perf_counter()
    if len(indices):
        model = ExtraTreesClassifier(**DOWNSTREAM, n_jobs=threads, random_state=seed)
        model.fit(bundle.X_train[:, indices], bundle.y_train)
        probability = model.predict_proba(bundle.X_test[:, indices])[:, 1]
    else:
        probability = np.full(len(bundle.y_test), np.mean(bundle.y_train))
    predicted = (probability >= .5).astype(int)
    return dict(roc_auc=float(roc_auc_score(bundle.y_test, probability)), accuracy=float(accuracy_score(bundle.y_test, predicted)),
                balanced_accuracy=float(balanced_accuracy_score(bundle.y_test, predicted)),
                f1=float(f1_score(bundle.y_test, predicted, zero_division=0)), seconds=time.perf_counter()-started,
                selected_count=len(indices))
