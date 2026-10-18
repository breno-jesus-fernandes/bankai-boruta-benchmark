"""Manifest-validated median/IQR reports; failures never become observations."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from .config import atomic_json, digest, SEEDS, PROTOCOL

QUANTILE_METHOD = "linear"


def distribution(values):
    if not values:
        return dict(median=None, q1=None, q3=None, iqr=None)
    q1, median, q3 = np.quantile(values, [.25, .5, .75], method=QUANTILE_METHOD)
    return dict(median=float(median), q1=float(q1), q3=float(q3), iqr=float(q3-q1))


def write_csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row)) or ["dataset", "competitor", "threads"]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def validated_results(root):
    manifests = sorted(Path(root).rglob("manifest.json"))
    if not manifests:
        raise ValueError("No manifests found")
    results, expected, issues, fingerprints = [], [], [], set()
    for path in manifests:
        manifest = json.loads(path.read_text())
        if digest({k: v for k, v in manifest.items() if k != "configuration_hash"}) != manifest["configuration_hash"]:
            raise ValueError(f"Manifest checksum mismatch: {path}")
        if manifest.get("protocol") not in (None, PROTOCOL, "paper-v2-a5-amd16"):
            raise ValueError("Unsupported benchmark protocol")
        fingerprints.add(digest(dict(source=manifest["source_hash"], packages=manifest["package_versions"], protocol=manifest.get("protocol", "paper-v1-a4"))))
        for spec in manifest["trials"]:
            expected.append(spec)
            result_path = path.parent.parent/spec["key"]
            if not result_path.exists():
                issues.append(dict(key=spec["key"], status="missing")); continue
            result = json.loads(result_path.read_text())
            for field in ("configuration_hash", "dataset", "competitor", "seed", "threads", "experiment_id", "suite", "mode"):
                if result[field] != spec[field]:
                    raise ValueError(f"Manifest mismatch {field}: {result_path}")
            if manifest.get("protocol") and result.get("protocol") != manifest["protocol"]:
                raise ValueError(f"Result protocol mismatch: {result_path}")
            if result["status"] != "success":
                issues.append(dict(key=spec["key"], status=result["status"]))
            results.append(result)
    if len(fingerprints) != 1:
        raise ValueError("Cannot combine different implementations or dependency versions")
    return results, expected, issues


def paired(results, numerator, denominator, field, threads=16, dataset="industrial"):
    groups = {method: {r["seed"]: r for r in results if r["competitor"] == method and r["dataset"] == dataset
                      and r["threads"] == threads and r["suite"] == "quality" and r["status"] == "success"}
              for method in (numerator, denominator)}
    values = []
    for seed in sorted(groups[numerator].keys() & groups[denominator].keys()):
        a, b = groups[numerator][seed], groups[denominator][seed]
        if field == "time":
            values.append(a["execution_metrics"]["fit_seconds"]/b["execution_metrics"]["fit_seconds"])
        else:
            values.append(100*(a["selection_metrics"]["recall"]-b["selection_metrics"]["recall"]))
    return values


def placeholder_values(results, mapping):
    rows = [r for r in results if r["status"] == "success" and r["suite"] == "quality"
            and r["dataset"] == mapping["dataset"] and r["threads"] == mapping["threads"]]
    groups = {alias: [r for r in rows if r["competitor"] == method] for alias, method in mapping["methods"].items()}
    complete = all({r["seed"] for r in group} == set(SEEDS) and all(r["mode"] == "full" for r in group) for group in groups.values())
    def median(alias, category, name):
        return distribution([r[category][name] for r in groups[alias]])["median"]
    tokens = {token: median(alias, "execution_metrics", "fit_seconds") for token, alias in mapping["time_tokens"].items()}
    for alias in groups:
        tokens["m"+alias] = median(alias, "execution_metrics", "peak_rss_gib")
        tokens["r"+alias] = median(alias, "selection_metrics", "recall")
    for suffix, alias in (("C", "CR"), ("G", "GR")):
        if alias not in groups: continue
        tokens["info"+suffix] = median(alias, "selection_metrics", "tp")
        tokens["ruido"+suffix] = median(alias, "selection_metrics", "fp")
    opts = dict(threads=mapping["threads"], dataset=mapping["dataset"])
    if "CA" in mapping["methods"]:
        tokens["razao"] = distribution(paired(results, mapping["methods"]["CA"], mapping["methods"]["CR"], "time", **opts))["median"]
        tokens["delta"] = distribution(paired(results, mapping["methods"]["CR"], mapping["methods"]["CA"], "recall", **opts))["median"]
    return tokens, complete


def aggregate(root, output, provisional=False, mapping_path=None):
    results, expected, issues = validated_results(root)
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    seen = set(); groups = {}
    for spec in expected:
        identity = (spec["suite"], spec["dataset"], spec["competitor"], spec["threads"], spec["seed"])
        if identity in seen:
            raise ValueError("Overlapping campaigns; aggregate them separately")
        seen.add(identity)
        key = (spec["suite"], spec["mode"], spec["dataset"], spec["competitor"], spec["threads"], spec["configuration_hash"])
        groups.setdefault(key, []).append(spec)
    summary = []
    for key, specs in groups.items():
        suite, mode, dataset, competitor, threads, cfg = key
        matched = [r for r in results if (r["suite"], r["mode"], r["dataset"], r["competitor"], r["threads"], r["configuration_hash"]) == key]
        successes = [r for r in matched if r["status"] == "success"]
        row = dict(suite=suite, mode=mode, dataset=dataset, competitor=competitor, threads=threads, configuration_hash=cfg,
                   expected_seeds=len(specs), successful_seeds=len(successes), failures=len(matched)-len(successes), missing=len(specs)-len(matched))
        for category, names in (("execution_metrics", ("fit_seconds", "peak_rss_gib", "delta_peak_gib", "completed_rounds", "seconds_per_round")),
                                ("selection_metrics", ("precision", "recall", "f1", "fdr", "tp", "fp", "fp_trap_noise", "fp_trap_noise_rate", "tentative_count")),
                                ("downstream_metrics", ("roc_auc", "accuracy", "balanced_accuracy", "f1", "seconds"))):
            for name in names:
                label = f"downstream_{name}" if category == "downstream_metrics" else name
                row.update({f"{label}_{stat}": value for stat, value in distribution([r[category][name] for r in successes if r[category].get(name) is not None]).items()})
        subtypes = {name for r in successes for name in r["selection_metrics"].get("subtype_recall", {})}
        for name in sorted(subtypes):
            row.update({f"recall_{name}_{stat}": value for stat, value in distribution([r["selection_metrics"]["subtype_recall"][name] for r in successes if r["selection_metrics"]["subtype_recall"].get(name) is not None]).items()})
        for category in ("intensity_recall",):
            for name in sorted({name for r in successes for name in r["selection_metrics"].get(category, {})}):
                row.update({f"{category}_{name}_{stat}": value for stat, value in distribution([r["selection_metrics"][category][name] for r in successes if r["selection_metrics"].get(category, {}).get(name) is not None]).items()})
        # Explicit buffers are diagnostics, never interchangeable with process RSS.
        numeric_diagnostics = {key for r in successes for key, value in (r.get("diagnostics") or {}).items() if isinstance(value, (int, float)) and not isinstance(value, bool)}
        for name in sorted(numeric_diagnostics):
            row.update({f"diagnostic_{name}_{stat}": value for stat, value in distribution([r["diagnostics"][name] for r in successes if isinstance((r.get("diagnostics") or {}).get(name), (int, float))]).items()})
        for reference in ("oracle", "all_features"):
            values = []
            for spec in specs:
                path = Path(root)/spec["experiment_id"]/"references"/dataset/f"seed{spec['seed']}.json"
                if path.exists():
                    values.append(json.loads(path.read_text())[reference]["roc_auc"])
            row.update({f"{reference}_auc_{stat}": value for stat, value in distribution(values).items()})
        summary.append(row)
    write_csv(output/"summary_by_dataset.csv", summary)
    scaling = []
    for row in summary:
        if row["suite"] != "scaling":
            continue
        same = [r for r in results if r["status"] == "success" and r["suite"] == "scaling" and r["dataset"] == row["dataset"] and r["competitor"] == row["competitor"]]
        baseline = {r["seed"]: r for r in same if r["threads"] == 1}
        values = [baseline[r["seed"]]["execution_metrics"]["fit_seconds"]/r["execution_metrics"]["fit_seconds"]
                  for r in same if r["threads"] == row["threads"] and r["seed"] in baseline]
        scaling.append(dict(dataset=row["dataset"], competitor=row["competitor"], threads=row["threads"], paired_seeds=len(values),
            **{f"speedup_{k}": v for k, v in distribution(values).items()},
            **{f"efficiency_{k}": v for k, v in distribution([v/row["threads"] for v in values]).items()}))
    write_csv(output/"thread_scaling.csv", scaling)
    manifests = [json.loads(p.read_text()) for p in Path(root).rglob("manifest.json")]
    current = all(m.get("protocol") == PROTOCOL for m in manifests)
    mapping = json.loads(Path(mapping_path or Path(__file__).with_name("config-paper.json" if current else "config-paper-v1.json")).read_text())
    tokens, placeholder_complete = placeholder_values(results, mapping)
    complete = placeholder_complete and not issues
    if not complete and not provisional:
        tokens = {key: None for key in tokens}
    atomic_json(output/"placeholder_replacements.json", {"{{"+key+"}}": value for key, value in tokens.items()})
    label = "FINAL" if complete else "PROVISIONAL — incomplete, smoke, or unavailable target cells"
    lines = ["% "+label]
    lines += ["\\expandafter\\def\\csname wmecai"+key+"\\endcsname{"+(f"{value:.4f}" if value is not None else "NA")+"}" for key, value in tokens.items()]
    (output/"wmecai_placeholders.tex").write_text("\n".join(lines)+"\n")
    def table(rows):
        lines = ["% "+label, "\\begin{tabular}{llrrrr}", "Dataset & Method & Threads & Seconds & RSS GiB & Recall \\\\", "\\hline"]
        for row in rows:
            def fmt(key):
                value = row.get(key+"_median")
                return "NA" if value is None else f"{value:.3f} [{row[key+'_q1']:.3f}, {row[key+'_q3']:.3f}]"
            method = row["competitor"].replace("_", "\\_")
            lines.append(f"{row['dataset']} & {method} & {row['threads']} & {fmt('fit_seconds')} & {fmt('peak_rss_gib')} & {fmt('recall')} \\\\")
        return "\n".join(lines+["\\end{tabular}"])+"\n"
    quality = [r for r in summary if r["suite"] == "quality"]
    (output/"wmecai_table1.tex").write_text(table([r for r in quality if r["competitor"] != "greedy_borutapy_lightgbm"]))
    if current:
        (output/"wmecai_lightgbm_greedy.tex").unlink(missing_ok=True)
    if not current: (output/"wmecai_lightgbm_greedy.tex").write_text(table([r for r in quality if r["competitor"] == "greedy_borutapy_lightgbm"]))
    atomic_json(output/"completeness.json", dict(final_paper_ready=complete, expected=len(expected),
        successful=sum(r["status"] == "success" for r in results), issues=issues, quantile_method=QUANTILE_METHOD))
    markdown = ["# "+label, "", f"Expected: {len(expected)}. Successful: {sum(r['status']=='success' for r in results)}. Missing/failed: {len(issues)}.", "",
        "| Dataset | Method | Threads | Seeds | Fit seconds, median [Q1, Q3] |", "|---|---|---:|---:|---|"]
    for row in summary:
        markdown.append(f"| {row['dataset']} | {row['competitor']} | {row['threads']} | {row['successful_seeds']}/{row['expected_seeds']} | {row['fit_seconds_median']} [{row['fit_seconds_q1']}, {row['fit_seconds_q3']}] |")
    (output/"summary.md").write_text("\n".join(markdown)+"\n")
    return complete


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default="results"); parser.add_argument("--output", default="reports")
    parser.add_argument("--provisional", action="store_true"); parser.add_argument("--mapping")
    parser.add_argument("--bucket"); parser.add_argument("--experiment", action="append")
    args = parser.parse_args()
    if args.bucket:
        import boto3
        s3 = boto3.client("s3")
        for experiment in args.experiment or []:
            for page in s3.get_paginator("list_objects_v2").paginate(Bucket=args.bucket, Prefix=experiment+"/"):
                for item in page.get("Contents", []):
                    key = item["Key"]
                    if key.endswith(".json"):
                        if ".." in Path(key).parts or Path(key).is_absolute():
                            raise ValueError("Unsafe result object key")
                        target = Path(args.results)/key; target.parent.mkdir(parents=True, exist_ok=True)
                        s3.download_file(args.bucket, key, str(target))
    aggregate(args.results, args.output, args.provisional, args.mapping)


if __name__ == "__main__":
    main()
