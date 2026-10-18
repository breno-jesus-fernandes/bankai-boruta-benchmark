"""Small parity and package-identity gate for the dedicated candidate image."""
import json
from pathlib import Path
import subprocess
import tempfile


def main():
    subprocess.run([
        "/opt/candidate/bin/python", "/opt/borutapy_max40_pilot.py", "--smoke",
    ], check=True)
    output = Path(tempfile.gettempdir()) / "exact-session-image-smoke.json"
    output.unlink(missing_ok=True)
    compare = ("/opt/compare_exact_session.py" if Path("/opt/compare_exact_session.py").is_file()
               else "/opt/boruta/benchmarks/compare_exact_session.py")
    subprocess.run([
        "/opt/candidate/bin/python", compare,
        "--reference-python", "/opt/reference/bin/python",
        "--candidate-python", "/opt/candidate/bin/python",
        "--rows", "2000", "--columns", "40", "--trees", "10",
        "--threads", "1", "--seed", "42", "--fixed-rounds", "0",
        "--repeats", "1", "--timeout-seconds", "600",
        "--output", str(output),
    ], check=True)
    result = json.loads(output.read_text())
    assert result["parity"] == "passed"
    reference, candidate = result["results"]
    assert reference["packages"]["bankai-boruta"] == "0.1.0a6"
    assert reference["packages"]["bankai-random-forest"] == "0.1.0a15"
    assert candidate["packages"]["bankai-boruta"] == "0.1.0a7"
    assert candidate["packages"]["bankai-random-forest"] == "0.1.0a16"
    assert candidate["diagnostics"].get("storage_mode") == "virtual_session"
    print("exact-session image packages and parity verified")


if __name__ == "__main__":
    main()
