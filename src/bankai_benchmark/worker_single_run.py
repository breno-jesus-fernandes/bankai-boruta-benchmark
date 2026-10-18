"""One trial per OS process. Set numerical thread controls before heavy imports."""
import argparse
import gc
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import threading
import time
import traceback

THREAD_VARIABLES = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "RAYON_NUM_THREADS")


def configure_threads(threads):
    if threads < 1:
        raise ValueError("threads must be positive")
    for variable in THREAD_VARIABLES:
        os.environ[variable] = str(threads if variable in ("OMP_NUM_THREADS", "RAYON_NUM_THREADS") else 1)
    if hasattr(os, "sched_getaffinity"):
        allowed = sorted(os.sched_getaffinity(0))
        from .topology import linux_topology, select_physical_cpus
        selected = select_physical_cpus(allowed, linux_topology(allowed), threads)
        os.sched_setaffinity(0, selected)
        if sorted(os.sched_getaffinity(0)) != selected:
            raise RuntimeError("Effective affinity differs from selected physical CPUs")
        return sorted(os.sched_getaffinity(0))
    if platform.system() == "Linux":
        raise RuntimeError("Linux requires verifiable CPU affinity")
    return None


def vmhwm():
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmHWM:"):
                return int(line.split()[1])*1024
    except OSError:
        pass
    return None


def cpu_model():
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    if platform.system() == "Darwin":
        import subprocess
        return subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
    return platform.processor()


def base_result(trial):
    from dataclasses import asdict
    from .config import SCHEMA_VERSION, PROTOCOL, GENERATOR_VERSION
    return dict(protocol=PROTOCOL, generator_version=GENERATOR_VERSION, schema_version=SCHEMA_VERSION, **{k: v for k, v in asdict(trial).items() if k != "warmup"},
        trial_id=trial.trial_id, configuration_hash=trial.configuration_hash, status="execution_failure",
        selection_metrics=None, execution_metrics=None, downstream_metrics=None, selected_indices=None,
        tentative_indices=None, diagnostics=None, provenance=None, error=None)


def run(trial, cache, output):
    from .config import atomic_json, source_hash
    result = base_result(trial)
    try:
        allowed = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None
        topology = None
        if allowed is not None:
            from .topology import linux_topology
            topology = linux_topology(allowed)
        affinity = configure_threads(trial.threads)
        import psutil
        import numpy as np
        from .datasets import load_dataset
        from .competitors import PreparedSelector
        from .metrics import selection_metrics, downstream
        bundle = load_dataset(cache)
        X = np.array(bundle.X_train, copy=True, order="C"); y = np.array(bundle.y_train, copy=True)
        # Drop the now-resident cache mappings before measuring the baseline.
        bundle.X_train = X; bundle.y_train = y
        prepared = PreparedSelector(trial)
        gc.collect()
        process = psutil.Process(); baseline = process.memory_info().rss
        reset = False
        if platform.system() == "Linux":
            try:
                Path("/proc/self/clear_refs").write_text("5\n"); reset = True
            except OSError:
                pass
        peak = [baseline]; stop = threading.Event()
        def poll():
            while not stop.wait(.005):
                peak[0] = max(peak[0], process.memory_info().rss)
        monitor = threading.Thread(target=poll, daemon=True); monitor.start()
        started = time.perf_counter()
        try:
            prepared.fit(X, y)
            duration = time.perf_counter()-started
            highwater = vmhwm()
            peak[0] = max(peak[0], process.memory_info().rss)
        finally:
            stop.set(); monitor.join()
        primary = max(peak[0], highwater or 0)
        selection = prepared.result()
        result.update(status="success", selected_indices=np.flatnonzero(selection.confirmed).tolist(),
            tentative_indices=np.flatnonzero(selection.tentative).tolist(), diagnostics=selection.diagnostics,
            selection_metrics=selection_metrics(selection.confirmed, bundle.relevant_features, bundle.feature_subtypes, selection.tentative, bundle.metadata.get("intensity_groups")),
            execution_metrics=dict(fit_seconds=duration, completed_rounds=selection.rounds,
                seconds_per_round=duration/selection.rounds if selection.rounds else None, baseline_rss_bytes=baseline,
                fit_polling_peak_bytes=peak[0], vmhwm_bytes=highwater, peak_rss_gib=primary/2**30,
                delta_peak_gib=max(0, primary-baseline)/2**30, highwater_reset=reset,
                highwater_scope="fit" if reset else "process_lifetime", memory_method="polling_and_vmhwm" if highwater else "polling"))
        result["provenance"] = dict(pid=os.getpid(), platform=platform.platform(), cpu=cpu_model(), logical_cpus=psutil.cpu_count(),
            physical_cpus=psutil.cpu_count(logical=False), affinity=affinity,
            topology=dict(status="verified" if topology is not None else "unavailable_macos_smoke",
                allowed_cpus=allowed, physical_core_ids=topology, selected_cpus=affinity, effective_affinity=affinity),
            cpu_vendor=next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("vendor_id")), None) if platform.system() == "Linux" else "unavailable", source_hash=source_hash(),
            thread_environment={k: os.environ[k] for k in THREAD_VARIABLES},
            packages={name: importlib.metadata.version(name) for name in ("numpy", "scipy", "scikit-learn", "bankai-boruta", "bankai-random-forest", "Boruta", "lightgbm")},
            effective_parameters=selection.effective_parameters, dataset_metadata=bundle.metadata,
            image_digest=os.environ.get("BENCHMARK_IMAGE_DIGEST"), task_arn=os.environ.get("BENCHMARK_TASK_ARN"),
            instance_identity=os.environ.get("BENCHMARK_INSTANCE_ID"), log_location=os.environ.get("BENCHMARK_LOG_LOCATION"))
        # End memory collection before any downstream fit.
        result["downstream_metrics"] = downstream(bundle, result["selected_indices"], trial.seed, trial.threads)
    except Exception as exc:
        result["status"] = "resource_failure" if isinstance(exc, MemoryError) else "execution_failure"
        result["error"] = dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
    atomic_json(output, result)
    return result["status"] == "success"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trial", required=True); parser.add_argument("--cache", required=True)
    parser.add_argument("--output", required=True); parser.add_argument("--reference", action="store_true")
    args = parser.parse_args()
    from .config import Trial, atomic_json
    trial = Trial(**json.loads(args.trial))
    if args.reference:
        configure_threads(trial.threads)
        from .datasets import load_dataset
        from .metrics import downstream
        bundle = load_dataset(args.cache)
        atomic_json(args.output, dict(schema_version=1, dataset_hash=bundle.metadata["configuration_hash"], seed=trial.seed,
            oracle=downstream(bundle, bundle.relevant_features, trial.seed, trial.threads),
            all_features=downstream(bundle, list(range(bundle.X_train.shape[1])), trial.seed, trial.threads)))
    else:
        raise SystemExit(0 if run(trial, args.cache, args.output) else 1)


if __name__ == "__main__":
    main()
