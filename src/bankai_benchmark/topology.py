"""Select nested sets of allowed CPUs, one logical processor per physical core."""
from pathlib import Path


def select_physical_cpus(allowed, topology, threads):
    if threads < 1:
        raise ValueError("threads must be positive")
    cores = {}
    for cpu in sorted(allowed):
        if cpu not in topology or any(value < 0 for value in topology[cpu]):
            raise RuntimeError(f"Unverifiable physical topology for CPU {cpu}")
        cores.setdefault(tuple(topology[cpu]), cpu)
    selected = sorted(cores.values())
    if len(selected) < threads:
        raise RuntimeError(f"Need {threads} physical cores; only {len(selected)} verifiable cores available")
    return selected[:threads]


def linux_topology(allowed, root=Path('/sys/devices/system/cpu')):
    topology = {}
    for cpu in sorted(allowed):
        directory = root/f'cpu{cpu}'/'topology'
        try:
            topology[cpu] = tuple(int((directory/name).read_text()) for name in ('physical_package_id', 'core_id'))
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"Cannot verify physical topology for CPU {cpu}") from exc
    return topology
