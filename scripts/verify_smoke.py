"""Local smoke matrix; isolated outputs, reports, and byte-identical resume."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from bankai_benchmark.config import PROFILES, PROTOCOL


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', choices=list(PROFILES))
    parser.add_argument('--results', default='verification/v2-a6-r5-local/results')
    parser.add_argument('--output', default='verification/v2-a6-r5-local/reports')
    args = parser.parse_args()
    command = [sys.executable, '-m', 'bankai_benchmark.orchestrator', 'smoke', '--experiment', PROTOCOL+'-smoke', '--results', args.results]
    if args.dataset: command += ['--dataset', args.dataset]
    started = time.perf_counter()
    subprocess.run(command, check=True)
    elapsed = time.perf_counter()-started
    paths = sorted((Path(args.results)/(PROTOCOL+'-smoke-quality')).glob('raw/**/*.json'))
    assert len(paths) == (4 if args.dataset else 16)
    before = {str(p): (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths}
    assert all(json.loads(p.read_text())['status'] == 'success' for p in paths)
    subprocess.run([sys.executable, '-m', 'bankai_benchmark.aggregate_latex', '--results', args.results, '--output', args.output, '--provisional'], check=True)
    subprocess.run(command, check=True)
    after = {str(p): (p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths}
    assert before == after, 'Resume changed a successful trial'
    assert not json.loads((Path(args.output)/'completeness.json').read_text())['final_paper_ready']
    assert not any('greedy' in p.name.lower() for p in Path(args.output).iterdir())
    print(json.dumps(dict(protocol=PROTOCOL, smoke_wall_seconds=elapsed, successful_trials=len(paths), resume_unchanged=True), indent=2))


if __name__ == '__main__': main()
