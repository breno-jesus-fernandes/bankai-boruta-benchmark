"""Run smoke, validate reports, and verify resume without refitting."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def main():
    started = time.perf_counter()
    subprocess.run([sys.executable, '-m', 'bankai_benchmark.orchestrator', 'smoke', '--experiment', 'smoke'], check=True)
    elapsed = time.perf_counter()-started
    paths = sorted(Path('results/smoke-quality/raw').rglob('*.json'))
    assert len(paths) == 7
    before = {str(p): (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths}
    assert all(json.loads(p.read_text())['status'] == 'success' for p in paths)
    subprocess.run([sys.executable, '-m', 'bankai_benchmark.aggregate_latex', '--provisional'], check=True)
    subprocess.run([sys.executable, '-m', 'bankai_benchmark.orchestrator', 'smoke', '--experiment', 'smoke'], check=True)
    after = {str(p): (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths}
    assert before == after, 'Resume refitted or changed a successful trial'
    assert not json.loads(Path('reports/completeness.json').read_text())['final_paper_ready']
    print(json.dumps(dict(smoke_wall_seconds=elapsed, successful_trials=len(paths), resume_unchanged=True), indent=2))


if __name__ == '__main__':
    main()
