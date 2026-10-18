"""Queue Industrial scaling at 4/8 threads; reuse original 16-thread observations.

The container runs its original measurement code. Only the trial grid is
restricted by the recorded entry-point wrapper; no worker source is edited.
"""
import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
import hashlib
import json
from pathlib import Path
import time

from bankai_benchmark.aggregate_latex import distribution, validated_results
from bankai_benchmark.aws_ecs import task_definition
from bankai_benchmark.config import HISTORICAL_COMPETITORS as COMPETITORS, SEEDS, atomic_json, digest
from bankai_benchmark.budget import LEDGER_KEY, TOTAL_BRL, RESERVE_BRL
from continue_quality import Controller, successful_exit


RUNNER = '''import bankai_benchmark.orchestrator as orchestrator
original_grid = orchestrator.trial_grid
def reduced_grid(experiment_id, mode, suite, dataset=None):
    if mode != "full" or suite != "scaling" or dataset not in (None, "industrial"):
        raise ValueError("This entry point permits Industrial full scaling only")
    from bankai_benchmark.config import PROTOCOL
    if PROTOCOL == "paper-v2-a5-amd16":
        raise ValueError("Historical scaling48 runner cannot execute protocol v2; use full --suite scaling")
    return tuple(sorted((t for t in original_grid(experiment_id, mode, suite, dataset)
                         if t.threads in (4, 8)),
                        key=lambda t: (-t.threads, t.competitor, t.seed)))
orchestrator.trial_grid = reduced_grid
from bankai_benchmark.ecs_entrypoint import main
main()
'''
RUNNER_SHA256 = hashlib.sha256(RUNNER.encode()).hexdigest()


def grid_keys(threads):
    return {(c, s, t) for c in COMPETITORS for s in SEEDS for t in threads}


def identity(row):
    return row['competitor'], row['seed'], row['threads']


def validate_grid(expected):
    if (len(expected) != 70 or {identity(r) for r in expected} != grid_keys((4, 8))
            or any(r['dataset'] != 'industrial' or r['suite'] != 'scaling'
                   or r['mode'] != 'full' for r in expected)):
        raise ValueError('Scaling manifest must contain exactly 70 Industrial trials at 4/8 threads')


def compatibility(row):
    p = row['provenance']
    return (p['source_hash'], digest(p['packages']), p['image_digest'], p['cpu'],
            p['logical_cpus'], p['physical_cpus'])


def compare(baseline_root, scaling_root, output):
    for root in (baseline_root, scaling_root):
        if any(json.loads(p.read_text()).get("protocol") == "paper-v2-a5-amd16" for p in Path(root).rglob("manifest.json")):
            raise ValueError("Historical scaling48 cannot reuse protocol v2 observations")
    baseline, _, _ = validated_results(baseline_root)
    baseline = [r for r in baseline if r['dataset'] == 'industrial'
                and r['suite'] == 'quality' and r['mode'] == 'full' and r['threads'] == 16]
    if (len(baseline) != 35 or {identity(r) for r in baseline} != grid_keys((16,))
            or any(r['status'] != 'success' for r in baseline)):
        raise ValueError('Need all 35 successful original quality observations at 16 threads')
    measured, expected, issues = validated_results(scaling_root)
    validate_grid(expected)
    successes = baseline + [r for r in measured if r['status'] == 'success']
    if len({compatibility(r) for r in successes}) != 1:
        raise ValueError('Image/source/dependencies/CPU topology differ; cannot reuse quality baseline')
    by_seed = {r['seed']: r['provenance']['dataset_metadata'] for r in baseline}
    for row in successes:
        if row['provenance']['dataset_metadata'] != by_seed[row['seed']]:
            raise ValueError('Dataset calibration/hash differs between thread counts')
        affinity = row['provenance']['affinity']
        if len(affinity) != row['threads']:
            raise ValueError('Affinity does not match requested thread count')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for method in COMPETITORS:
        four = {r['seed']: r for r in successes if r['competitor'] == method and r['threads'] == 4}
        for threads in (4, 8, 16):
            records = [r for r in successes if r['competitor'] == method and r['threads'] == threads]
            pairs = [four[r['seed']]['execution_metrics']['fit_seconds'] / r['execution_metrics']['fit_seconds']
                     for r in records if r['seed'] in four]
            failed = sum(r['status'] != 'success' for r in measured if r['competitor'] == method and r['threads'] == threads)
            row = dict(competitor=method, threads=threads, expected_seeds=5, successful_seeds=len(records),
                       failures=failed, missing=5-len(records)-failed, reused_quality=threads == 16,
                       baseline_threads=4, paired_seeds=len(pairs))
            for category, names in [('execution_metrics', ['fit_seconds', 'peak_rss_gib']),
                                    ('selection_metrics', ['precision', 'recall', 'f1']),
                                    ('downstream_metrics', ['roc_auc'])]:
                for name in names:
                    row.update({f'{name}_{k}': v for k,v in distribution([r[category][name] for r in records]).items()})
            row.update({f'speedup_vs_4_{k}': v for k,v in distribution(pairs).items()})
            row.update({f'relative_efficiency_vs_4_{k}': v
                        for k,v in distribution([v/(threads/4) for v in pairs]).items()})
            rows.append(row)
    with (output/'thread_scaling.csv').open('w', newline='') as handle:
        writer=csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    complete = not issues and len(measured) == 70 and all(r['status'] == 'success' for r in measured)
    atomic_json(output/'completeness.json', dict(complete=complete, new_expected=70,
        new_successful=sum(r['status'] == 'success' for r in measured), reused_successful=35,
        issues=issues, baseline_threads=4, runner_sha256=RUNNER_SHA256))
    atomic_json(output/'origins.json', [dict(competitor=r['competitor'], seed=r['seed'], threads=r['threads'],
        suite=r['suite'], experiment_id=r['experiment_id'], trial_id=r['trial_id'],
        configuration_hash=r['configuration_hash'], reused_quality=r['threads']==16) for r in successes])
    lines=['# '+('COMPLETE' if complete else 'PROVISIONAL'), '',
        'Industrial; five seeds per method/thread. Original quality measurements at 16 threads are reused.',
        'Speedup = paired T4/Tt. Relative efficiency = speedup/(t/4); no one-thread efficiency is claimed.', '',
        '| Method | Threads | Seeds | Fit seconds, median | Peak GiB, median | Paired speedup vs 4 |',
        '|---|---:|---:|---:|---:|---:|']
    for r in rows:
        def fmt(key):
            return 'NA' if r[key] is None else f'{r[key]:.3f}'
        lines.append(f"| {r['competitor']} | {r['threads']} | {r['successful_seeds']}/5 | {fmt('fit_seconds_median')} | {fmt('peak_rss_gib_median')} | {fmt('speedup_vs_4_median')} |")
    (output/'summary.md').write_text('\n'.join(lines)+'\n')
    return complete


class ScalingController(Controller):
    def sync(self):
        prefix = self.args.experiment + '-scaling/'
        for page in self.s3.get_paginator('list_objects_v2').paginate(Bucket=self.args.bucket, Prefix=prefix):
            for item in page.get('Contents', []):
                key=item['Key']
                if not key.endswith('.json') or '..' in Path(key).parts:
                    continue
                path=self.results/key
                if not path.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    temporary=path.with_suffix('.download')
                    self.s3.download_file(self.args.bucket,key,str(temporary))
                    temporary.replace(path)
        if not list(self.results.rglob('manifest.json')):
            return [], [], []
        records, expected, issues = validated_results(self.results)
        validate_grid(expected)
        return records, expected, issues

    def monitor(self, dataset, stage):
        deadline=datetime.fromisoformat(stage['shutdown_at'])
        while True:
            rows, expected, issues=self.sync()
            if rows:
                compare(self.args.baseline_directory,self.results,self.report)
            successful=sum(r['status']=='success' for r in rows)
            failures=sum(r['status']!='success' for r in rows)
            self.summary(f'Escala 4/8: {successful}/70 novos; 35 reutilizados; falhas {failures}')
            response=self.ecs.describe_tasks(cluster=self.args.cluster,tasks=stage['tasks'])
            if response.get('failures') or len(response['tasks']) != 1:
                raise RuntimeError('Scaling task state unavailable')
            task=response['tasks'][0]
            if task['lastStatus']=='STOPPED':
                if not successful_exit(task) or successful != 70 or issues:
                    raise RuntimeError(f'Scaling stopped/incomplete: {successful}/70; {task.get("stoppedReason")}')
                stage.update(status='complete',completed_at=datetime.now(timezone.utc).isoformat())
                self.save()
                return
            if failures:
                raise RuntimeError('Scaling trial failed; no automatic retry')
            if datetime.now(timezone.utc)>=deadline:
                raise TimeoutError('Three-hour scaling cap reached; completed results preserved')
            time.sleep(60)

    def run(self):
        if self.state['stages']:
            raise RuntimeError('Scaling already attempted; refusing a duplicate paid launch')
        existing, expected, issues = self.sync()
        if expected:
            if len(existing)==70 and not issues:
                compare(self.args.baseline_directory,self.results,self.report)
                self.summary('Escala ja completa no S3; relatorio gerado sem novo lancamento',notify=True)
                return
            raise RuntimeError('Existing scaling manifest/results require review before a new paid launch')
        # Queue locally without reserving funds or creating paid capacity while quality runs.
        self.summary('Escala 4/8 na fila; aguardando qualidade terminar; nenhuma instancia nova',notify=True)
        while True:
            quality=Path(self.args.quality_directory)
            status=(quality/'status.txt').read_text()
            if 'PARADO' in status:
                raise RuntimeError('Quality controller stopped; review before scaling')
            record=json.loads((quality/'controller.json').read_text())
            if all(record['stages'].get(d,{}).get('status')=='complete'
                   for d in ('credito','bioinformatica','ciberseguranca')):
                rows, expected, issues=validated_results(quality/'results')
                if len(rows)==140 and not issues and all(r['status']=='success' for r in rows):
                    try:
                        self.assert_idle_cluster()
                        break
                    except RuntimeError:
                        pass
            self.summary('Escala 4/8 na fila; aguardando qualidade e encerramento do host atual')
            time.sleep(60)
        # The new definition changes orchestration/grid only, preserving the measured image.
        with self.s3.get_object(Bucket=self.args.bucket,Key=LEDGER_KEY)['Body'] as body:
            ledger=json.load(body)
        allocated=sum((Decimal(r['reserved_brl']) for r in ledger['launches'].values()),Decimal(0))
        if allocated + Decimal('60') > TOTAL_BRL - RESERVE_BRL:
            raise RuntimeError('Insufficient remaining allocation for the bounded three-hour scaling run')
        old=self.ecs.describe_task_definition(taskDefinition=self.args.task_definition)['taskDefinition']
        if old['containerDefinitions'][0]['image'] != self.args.image:
            raise RuntimeError('Verified image changed')
        outputs={'ExecutionRole':old['executionRoleArn'],'TaskRole':old['taskRoleArn'],
                 'Logs':old['containerDefinitions'][0]['logConfiguration']['options']['awslogs-group']}
        definition=task_definition(self.args.experiment+'-scaling48',self.args.image,'us-east-1',outputs)
        definition['containerDefinitions'][0]['entryPoint']=['/app/.venv/bin/python','-c',RUNNER]
        response=self.ecs.register_task_definition(**definition)
        self.args.task_definition=response['taskDefinition']['taskDefinitionArn']
        self.state.update(task_definition=self.args.task_definition,runner_sha256=RUNNER_SHA256,
                          allowed_threads=[4,8],reuse_threads=16,reserved_brl='60',max_seconds=10800)
        self.save()
        source=self.group(self.args.source_fleet)
        try:
            stage=self.start('scaling48',source,suite='scaling',target_dataset='industrial',reservation_units=3)
            self.monitor('scaling48',stage)
        finally:
            stage=self.state['stages'].get('scaling48')
            if stage:
                self.cleanup(stage)
            self.sync()
            if list(self.results.rglob('manifest.json')):
                compare(self.args.baseline_directory,self.results,self.report)
        self.summary('Escala concluida: 70/70 novos + 35 reutilizados; host desligado; relatorio pronto',notify=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('profile','bucket','experiment','cluster','source-fleet','task-definition','image','directory',
                 'quality-directory','baseline-directory'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--notify',action='store_true')
    args=parser.parse_args()
    directory=Path(args.directory); directory.mkdir(parents=True,exist_ok=True)
    with (directory/'controller.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        controller=ScalingController(args)
        try:
            controller.run()
        except Exception as exc:
            controller.summary(f'PARADO: {type(exc).__name__}: {exc}',notify=True)
            raise


if __name__=='__main__':
    main()
