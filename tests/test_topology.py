import pytest
from bankai_benchmark.topology import select_physical_cpus, linux_topology


def test_smt_nested_and_restricted():
    topology = {2: (0, 0), 4: (0, 1), 8: (0, 0), 10: (0, 1), 20: (1, 0), 22: (1, 1)}
    assert select_physical_cpus(topology, topology, 4) == [2, 4, 20, 22]
    assert select_physical_cpus(topology, topology, 2) == [2, 4]
    assert select_physical_cpus([8, 10, 20], topology, 2) == [8, 10]
    with pytest.raises(RuntimeError, match='physical cores'):
        select_physical_cpus([2, 8], topology, 2)
    with pytest.raises(RuntimeError, match='Unverifiable'):
        select_physical_cpus([99], topology, 1)


def test_sysfs_fixture(tmp_path):
    for cpu, core in ((3, 0), (9, 1)):
        directory = tmp_path/f'cpu{cpu}'/'topology'
        directory.mkdir(parents=True)
        (directory/'physical_package_id').write_text('0')
        (directory/'core_id').write_text(str(core))
    assert linux_topology([3, 9], tmp_path) == {3: (0, 0), 9: (0, 1)}
    with pytest.raises(RuntimeError): linux_topology([4], tmp_path)


def test_full_scaling_sets_are_nested_with_smt():
    topology = {cpu: (cpu//16, cpu%16) for cpu in range(32)}
    # Add sibling threads to both sockets; physical IDs repeat within sockets.
    topology.update({cpu+64: core for cpu,core in list(topology.items())})
    previous=[]
    for threads in (1,2,4,8,16):
        selected=select_physical_cpus(topology,topology,threads)
        assert selected[:len(previous)] == previous
        assert len({topology[cpu] for cpu in selected}) == threads
        previous=selected
