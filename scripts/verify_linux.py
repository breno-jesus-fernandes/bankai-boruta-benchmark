"""Container acceptance: all twelve r4 trials, Linux VmHWM and exact CPU affinity."""
import json
from pathlib import Path
import subprocess
import sys

subprocess.run([sys.executable, '-m', 'bankai_benchmark.orchestrator', 'smoke', '--experiment', 'linux-smoke'], check=True)
rows = [json.loads(p.read_text()) for p in Path('results/linux-smoke-quality/raw').rglob('*.json')]
assert len(rows) == 12
for row in rows:
    assert row['status'] == 'success', row['error']
    assert row['protocol'] == 'paper-v2-a5-amd16-r4'
    assert row['execution_metrics']['vmhwm_bytes'] > 0
    assert row['execution_metrics']['memory_method'] == 'polling_and_vmhwm'
    assert len(row['provenance']['affinity']) == 1
    assert row['provenance']['topology']['status'] == 'verified'
    assert row['provenance']['thread_environment']['OPENBLAS_NUM_THREADS'] == '1'
    if row['competitor'] == 'bankai_native_extra_tree':
        assert row['diagnostics']['path'] == 'rust'
print(json.dumps(dict(linux_acceptance='passed', trials=[dict(competitor=r['competitor'],
    peak_rss_gib=r['execution_metrics']['peak_rss_gib'], highwater_reset=r['execution_metrics']['highwater_reset'],
    affinity=r['provenance']['affinity'], path=r['diagnostics']['path']) for r in rows]), indent=2))
