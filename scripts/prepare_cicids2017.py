"""Download and prepare CIC-IDS2017 (MachineLearningCSV) for the native-shadow benchmark.

Source: the eight original MachineLearningCSV files mirrored on Hugging Face at
a pinned revision, each checked against its LFS SHA256. Preparation:
concatenate the days, label BENIGN as 0 and every attack as 1, drop rows with
non-finite values, cast the 78 features to float32, drop duplicate rows
(features and label, after the cast) and split 70/30 stratified with seed 0.
Constant and duplicated columns are kept: the selector has to reject them.

Writes {train,test}-X.f32 (row-major float32), {train,test}-y.i32 and
manifest.json with shapes, counts and output hashes.

Usage: python scripts/prepare_cicids2017.py OUTPUT_DIR [--downloads DIR] [--rows-per-file N]
--rows-per-file reads only the first N rows of each day, for smoke tests.
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

REPOSITORY = "c01dsnap/CIC-IDS2017"
REVISION = "4e9edfa727f800b6f595bc2ee7420527156562b2"
FILES = {
    "Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv": "6ff1580f5f81c0ae28a26f7631721018577f5f7c5e0feac28b795fcfe7b411ee",
    "Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv": "ca1824c51bfbb7b3c72290a11be04366ba8815878c6a1cc5c44cb1cee269e99b",
    "Friday-WorkingHours-Morning.pcap_ISCX.csv": "53a41c24d570ea83b7ac55b2e94df94e7a8216aeb80a2af0246b6bc8bb543000",
    "Monday-WorkingHours.pcap_ISCX.csv": "852c4beb34eda186f32561fa79df7a0747e92e1a6535b01270820dd9ffe17f34",
    "Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv": "6bcda3857c2504676034e3ea57762d38393cc734cb377a726bd5cb153961b1b5",
    "Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv": "d67066211fb1689c78406f1506f4c44704ecb92088353d5c96d96d6474eb819d",
    "Tuesday-WorkingHours.pcap_ISCX.csv": "52b8692ae8c7d2ed04671fe2b98335693c0a92c7ab157d8c8b534d6523080851",
    "Wednesday-workingHours.pcap_ISCX.csv": "893c27dc968bf7a8adef1689f90be55ca4a4dc3088fb63d6ff247ac56856df2a",
}
TEST_SIZE, SPLIT_SEED = .3, 0


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(folder):
    folder.mkdir(parents=True, exist_ok=True)
    for name, expected in FILES.items():
        path = folder / name
        if not path.exists() or sha256(path) != expected:
            url = f"https://huggingface.co/datasets/{REPOSITORY}/resolve/{REVISION}/{name}"
            urllib.request.urlretrieve(url, path)
        if sha256(path) != expected:
            raise ValueError(f"{name} does not match its pinned SHA256")


def load(folder, rows_per_file=None):
    features, labels, columns, raw, nonfinite = [], [], None, 0, 0
    for name in sorted(FILES):
        frame = pd.read_csv(folder / name, encoding="latin-1", low_memory=False, nrows=rows_per_file)
        frame.columns = [column.strip() for column in frame.columns]
        label = frame.pop("Label").astype(str).str.strip()
        if columns is None:
            columns = list(frame.columns)
        if list(frame.columns) != columns:
            raise ValueError(f"{name} has different feature columns")
        values = frame.to_numpy(np.float64)
        finite = np.isfinite(values).all(axis=1)
        raw += len(values)
        nonfinite += int((~finite).sum())
        features.append(values[finite].astype(np.float32))
        labels.append((label.to_numpy()[finite] != "BENIGN").astype(np.int32))
    return np.concatenate(features), np.concatenate(labels), columns, raw, nonfinite


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--downloads", type=Path)
    parser.add_argument("--rows-per-file", type=int)
    args = parser.parse_args()
    output, downloads = args.output, args.downloads or args.output / "csv"
    download(downloads)
    X, y, columns, raw, nonfinite = load(downloads, args.rows_per_file)
    frame = pd.DataFrame(X)
    frame["label"] = y
    unique = ~frame.duplicated(keep="first").to_numpy()
    del frame
    X, y = np.ascontiguousarray(X[unique]), y[unique]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=TEST_SIZE, stratify=y, random_state=SPLIT_SEED)
    output.mkdir(parents=True, exist_ok=True)
    manifest = dict(source=f"https://huggingface.co/datasets/{REPOSITORY}", revision=REVISION, files=FILES,
        columns=columns, raw_rows=raw, nonfinite_rows=nonfinite, duplicate_rows=int((~unique).sum()),
        rows=len(y), positive_rate=float(y.mean()), test_size=TEST_SIZE, split_seed=SPLIT_SEED,
        rows_per_file=args.rows_per_file)
    for split, features, target in (("train", X_train, y_train), ("test", X_test, y_test)):
        np.ascontiguousarray(features, dtype="<f4").tofile(output / f"{split}-X.f32")
        np.asarray(target, dtype="<i4").tofile(output / f"{split}-y.i32")
        manifest[split] = dict(shape=list(features.shape), positives=int(target.sum()),
            X_sha256=sha256(output / f"{split}-X.f32"), y_sha256=sha256(output / f"{split}-y.i32"))
    (output / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(json.dumps({k: manifest[k] for k in ("raw_rows", "nonfinite_rows", "duplicate_rows", "rows", "positive_rate")}
        | {"train": manifest["train"]["shape"], "test": manifest["test"]["shape"]}))


if __name__ == "__main__":
    main()
