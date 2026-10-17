from dataclasses import asdict
import json
import subprocess
import sys
import pytest
from bankai_benchmark.config import Trial,atomic_json,trial_grid
from bankai_benchmark.datasets import cache_dataset
from bankai_benchmark.orchestrator import ensure_manifest,execute,manifest_for,runnable,upload,restore,run_trial,require_public_release

def test_grids_and_resume(tmp_path):
    assert len(trial_grid('x','smoke','quality')) == 7
    assert len(trial_grid('x','smoke-matrix','quality')) == 112
    assert len(trial_grid('x','full','quality')) == 140
    assert len(trial_grid('x','full','scaling')) == 175
    trials=trial_grid('x','smoke','quality');m=manifest_for(trials);p=tmp_path/'manifest.json'
    ensure_manifest(p,m);ensure_manifest(p,m)
    with pytest.raises(ValueError):ensure_manifest(p,dict(m,mode='full'))
    result=tmp_path/'result.json';assert runnable(result,trials[0])
    atomic_json(result,dict(configuration_hash=trials[0].configuration_hash,status='success'))
    assert not runnable(result,trials[0]) and runnable(result,trials[0],overwrite=True)
    atomic_json(result,dict(configuration_hash=trials[0].configuration_hash,status='timeout'))
    assert not runnable(result,trials[0]) and runnable(result,trials[0],retry_failed=True)
    atomic_json(result,dict(configuration_hash='bad',status='success'))
    with pytest.raises(ValueError):runnable(result,trials[0])

def test_timeout_cleanup(tmp_path):
    import psutil,time
    pidfile=tmp_path/'pid'
    code="import subprocess,time,pathlib;p=subprocess.Popen(['sleep','60']);pathlib.Path("+repr(str(pidfile))+").write_text(str(p.pid));time.sleep(60)"
    with pytest.raises(subprocess.TimeoutExpired):execute([sys.executable,'-c',code],.5)
    pid=int(pidfile.read_text())
    def exited():
        try:
            return psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return True
    for _ in range(50):
        if exited():break
        time.sleep(.01)
    assert exited()


def test_fresh_worker(tmp_path):
    trial=Trial('test-quality','quality','smoke','industrial','bankai_classic_native',42,1)
    cache=cache_dataset(tmp_path/'cache','industrial',42,'smoke');output=tmp_path/'success.json'
    result=run_trial(trial,cache,output,120);m=result['execution_metrics']
    assert result['status'] == 'success' and m['peak_rss_gib'] >= m['baseline_rss_bytes']/2**30
    assert m['delta_peak_gib'] >= 0
    assert result['provenance']['pid'] != __import__('os').getpid()
    assert result['provenance']['thread_environment']['OMP_NUM_THREADS'] == '1'
    if sys.platform == 'linux':assert len(result['provenance']['affinity']) == 1 and m['vmhwm_bytes'] > 0
    failure=run_trial(trial,tmp_path/'nonexistent',tmp_path/'failure.json',120)
    assert failure['status'] == 'execution_failure' and failure['execution_metrics'] is None
    assert failure['error']['type'] == 'FileNotFoundError'

def test_timeout_result_replaces_old_file(tmp_path,monkeypatch):
    trial=trial_grid('x','smoke','quality')[0];p=tmp_path/'result.json'
    atomic_json(p,dict(status='success'))
    def timeout(*args):raise subprocess.TimeoutExpired('worker',.1)
    monkeypatch.setattr('bankai_benchmark.orchestrator.execute',timeout)
    result=run_trial(trial,tmp_path,p,.1)
    assert result['status'] == 'timeout' and result['execution_metrics'] is None

def test_upload_retry_restore(tmp_path,monkeypatch):
    from botocore.exceptions import EndpointConnectionError,ClientError
    import io
    class S3:
        calls=0
        def upload_file(self,*args):
            self.calls+=1
            if self.calls<3:raise EndpointConnectionError(endpoint_url='https://example.invalid')
        def get_object(self,**kwargs):return {'Body':io.BytesIO(b'{"status":"success"}')}
    s3=S3();monkeypatch.setattr('bankai_benchmark.orchestrator.time.sleep',lambda _:None)
    upload(s3,tmp_path/'result','bucket','key');assert s3.calls == 3
    p=tmp_path/'restored.json';restore(s3,'bucket','key',p);assert json.loads(p.read_text())['status'] == 'success'
    class Fail:
        def upload_file(self,*args):raise ClientError({'Error':{'Code':'AccessDenied'}},'PutObject')
    with pytest.raises(ClientError):upload(Fail(),p,'bucket','key')
    assert p.exists()

def test_paper_runs_are_gated():
    with pytest.raises(RuntimeError,match='public Bankai release'):require_public_release()
