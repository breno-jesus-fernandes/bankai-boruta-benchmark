import csv
import importlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]/'scripts'))
scaling=importlib.import_module('scaling48')

from bankai_benchmark.config import HISTORICAL_COMPETITORS as COMPETITORS, SEEDS, Trial, atomic_json
from bankai_benchmark.orchestrator import manifest_for
from test_aggregation import fake_result


def test_container_wrapper_only_restricts_grid_and_keeps_original_worker(monkeypatch):
    import bankai_benchmark.orchestrator as orchestrator
    import bankai_benchmark.ecs_entrypoint as entry
    original=orchestrator.trial_grid
    monkeypatch.setattr(orchestrator,'trial_grid',original)
    seen=[]
    monkeypatch.setattr(entry,'main',lambda:seen.extend(orchestrator.trial_grid('test-scaling','full','scaling')))
    with pytest.raises(ValueError, match='Historical scaling48'):
        exec(scaling.RUNNER,{})


def historical_manifest(trials):
    m=manifest_for(trials)
    m.pop('protocol',None)
    m['configuration_hash']=__import__('bankai_benchmark.config',fromlist=['digest']).digest({k:v for k,v in m.items() if k!='configuration_hash'})
    return m


def campaign(tmp_path):
    baseline=tmp_path/'baseline'; measured=tmp_path/'measured'
    def make(root, suite, threads):
        trials=[Trial('test-'+suite,suite,'full','industrial',c,s,t)
                for c in COMPETITORS for s in SEEDS for t in threads]
        atomic_json(root/('test-'+suite)/'manifest.json',historical_manifest(trials))
        for t in trials:
            four=[2,100,3,100,4][t.seed-42]
            eight=[1,100,1,100,1][t.seed-42]
            duration=four if t.threads==4 else eight if t.threads==8 else eight/2
            row=fake_result(t,duration)
            row['provenance']={'source_hash':'same-source','packages':{'bankai-boruta':'0.1.0a4'},
                'image_digest':'repo@sha256:unchanged','cpu':'same-cpu','logical_cpus':16,'physical_cpus':8,
                'dataset_metadata':{'seed':t.seed,'configuration_hash':'dataset-'+str(t.seed)},
                'affinity':list(range(t.threads))}
            atomic_json(root/t.key,row)
        return trials
    make(baseline,'quality',[16]);trials=make(measured,'scaling',[4,8])
    return baseline,measured,trials


def test_report_pairs_seeds_reuses_16_and_uses_four_thread_baseline(tmp_path):
    baseline, measured, _=campaign(tmp_path)
    output=tmp_path/'report'
    assert scaling.compare(baseline,measured,output)
    rows=list(csv.DictReader((output/'thread_scaling.csv').open()))
    assert len(rows)==21
    eight=next(r for r in rows if r['threads']=='8')
    assert float(eight['speedup_vs_4_median'])==2
    assert float(eight['relative_efficiency_vs_4_median'])==1
    assert eight['paired_seeds']=='5' and eight['baseline_threads']=='4'
    sixteen=next(r for r in rows if r['threads']=='16')
    assert float(sixteen['speedup_vs_4_median'])==4
    origins=json.loads((output/'origins.json').read_text())
    reused=[r for r in origins if r['reused_quality']]
    assert len(reused)==35 and {r['suite'] for r in reused}=={'quality'}
    assert {r['threads'] for r in origins}=={4,8,16}


@pytest.mark.parametrize('change',['image','dataset','affinity'])
def test_report_rejects_incompatible_baseline(tmp_path,change):
    baseline,measured,trials=campaign(tmp_path)
    path=measured/trials[0].key;row=json.loads(path.read_text())
    if change=='image':row['provenance']['image_digest']='different'
    if change=='dataset':row['provenance']['dataset_metadata']['configuration_hash']='different'
    if change=='affinity':row['provenance']['affinity']=[0]
    atomic_json(path,row)
    with pytest.raises(ValueError):scaling.compare(baseline,measured,tmp_path/'report')


def test_partial_results_are_provisional_and_failure_is_not_zero_time(tmp_path):
    baseline,measured,trials=campaign(tmp_path)
    path=measured/trials[0].key;row=json.loads(path.read_text())
    row.update(status='timeout',execution_metrics=None)
    atomic_json(path,row)
    assert not scaling.compare(baseline,measured,tmp_path/'report')
    report=json.loads((tmp_path/'report/completeness.json').read_text())
    assert report['new_successful']==69 and not report['complete']


def test_three_hour_shutdown_readback_failure_blocks_capacity(tmp_path,monkeypatch):
    from datetime import datetime,timezone
    from unittest.mock import Mock
    from test_quality_controller import bare_controller,controller_module
    controller=bare_controller(tmp_path)
    monkeypatch.setattr(controller_module,'reserve',Mock())
    monkeypatch.setattr(controller_module,'arm',Mock(return_value=datetime(2099,1,1,tzinfo=timezone.utc)))
    controller.asg.describe_scheduled_actions.return_value={'ScheduledUpdateGroupActions':[]}
    with pytest.raises(RuntimeError,match='AWS shutdown verification failed'):
        controller.start('scaling48',{'LaunchTemplate':{'LaunchTemplateId':'lt-id','Version':'1'},'VPCZoneIdentifier':'subnet'},
                         suite='scaling',target_dataset='industrial',reservation_units=3)
    assert controller_module.reserve.call_count==3
    controller.asg.update_auto_scaling_group.assert_not_called()
    controller.ecs.run_task.assert_not_called()
