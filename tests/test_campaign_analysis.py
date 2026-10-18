from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from analyze_campaign import paired_comparisons
from bankai_benchmark.config import HISTORICAL_COMPETITORS as COMPETITORS,SEEDS,Trial
from test_aggregation import fake_result


def test_quality_comparisons_pair_seeds_before_summary_and_check_selection_parity():
    rows=[]
    for dataset in ('industrial','credito','bioinformatica','ciberseguranca'):
        for method in COMPETITORS:
            for i,seed in enumerate(SEEDS):
                seconds=([1,100,1,100,1] if method=='bankai_classic_native' else [2,100,3,100,4])[i]
                row=fake_result(Trial('test-quality','quality','full',dataset,method,seed,16),seconds)
                row['selected_indices']=[2] if method=='bankai_classic_adapter' and seed==46 else [1]
                row['tentative_indices']=[]
                row['execution_metrics']['peak_rss_gib']=2 if method=='bankai_classic_native' else 4
                rows.append(row)
    comparisons=paired_comparisons(list(reversed(rows)))
    pair=next(r for r in comparisons if r['dataset']=='industrial' and r['method_b']=='bankai_classic_adapter')
    assert pair['paired_seeds']==5
    assert pair['speedup_a_over_b_median']==2
    assert pair['fit_reduction_a_pct_median']==50
    assert pair['rss_reduction_a_pct_median']==50
    assert pair['identical_confirmed_sets']==4
