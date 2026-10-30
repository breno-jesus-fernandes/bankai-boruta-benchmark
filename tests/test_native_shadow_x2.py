import importlib.util
from pathlib import Path
import sys

import pytest

from bankai_benchmark.aws_ecs import infrastructure
from bankai_benchmark.config import PROFILES, RELEVANT_COUNTS, profile

SCRIPTS = Path(__file__).parents[1]/'scripts'


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_full2x_doubles_rows_and_columns_only():
    for name, cfg in PROFILES.items():
        doubled = profile(name, 'full2x')
        assert (doubled.n, doubled.p) == (2*cfg.n, 2*cfg.p)
        assert (doubled.trees, doubled.depth, doubled.bins, doubled.max_features) == (cfg.trees, cfg.depth, cfg.bins, cfg.max_features)
        assert doubled.p - RELEVANT_COUNTS[name] > cfg.p
    assert profile('industrial', 'full') == PROFILES['industrial']


def test_pilot_scale_keeps_real_data_unscaled():
    pilot = load('native_shadow_pilot')
    assert pilot.mode('industrial', 2) == 'full2x' and pilot.mode('industrial', 1) == 'full'
    assert pilot.mode('cicids2017', 2) == 'full'
    assert pilot.config('cicids2017', 2) == PROFILES['ciberseguranca']


def test_runner_targets_the_32_core_host():
    pytest.importorskip('boto3')
    runner = load('run_native_shadow_aws')
    outputs = dict(ExecutionRole='execution', TaskRole='task', Logs='/bankai/x')
    definition = runner.task_definition(outputs, 'repo@sha256:'+'a'*64, ['industrial'], ['bankai_exact'], [42], 32, 5,
                                        'c7a.8xlarge', 2)
    assert (definition['cpu'], definition['memory']) == ('32768', '59392')
    command = definition['containerDefinitions'][0]['command']
    assert command[command.index('--scale')+1] == '2' and command[command.index('--threads')+1] == '32'
    template = infrastructure('native-shadow-max40-v1', 'bucket', ['subnet'], ['sg'], runner.machine('c7a.8xlarge'))
    data = template['Resources']['LaunchTemplate']['Properties']['LaunchTemplateData']
    assert data['InstanceType'] == 'c7a.8xlarge' and data['CpuOptions'] == {'CoreCount': 32, 'ThreadsPerCore': 1}
    # The default keeps the published 16-core runs reproducible.
    default = runner.task_definition(outputs, 'repo@sha256:'+'a'*64, ['industrial'], ['bankai_exact'], [42], 16, 5)
    assert (default['cpu'], default['memory']) == ('16384', '28672')
    assert runner.INSTANCES['c7a.8xlarge']['hour_usd'] == 2*runner.INSTANCES['c7a.4xlarge']['hour_usd']
