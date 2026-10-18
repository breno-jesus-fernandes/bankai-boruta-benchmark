# Dependency licenses

`LICENSE` covers new benchmark code. Third-party components keep their own
licenses and notices; the lockfile records the resolved distributions.

| Component | License |
|---|---|
| bankai-boruta | GPL-3.0-or-later; upstream/COPYING |
| bankai-random-forest | GPL-3.0-or-later |
| BorutaPy | BSD-3-Clause |
| NumPy, SciPy, scikit-learn, pandas, joblib | BSD family |
| LightGBM | MIT |
| psutil | BSD-3-Clause |
| boto3, botocore, AWS CRT | Apache-2.0 |
| pytest | MIT |

Bankai packages are installed from their public distributions. Historical
patches under `upstream/` retain upstream GPL terms, not the benchmark MIT
license. Transitive and system libraries carry their distribution notices;
consult installed `.dist-info` metadata for exact version-specific terms.

Protocolo v2 fixa bankai-boruta==0.1.0a5 e bankai-random-forest==0.1.0a15 em pyproject/uv.lock. Os seis artefatos PyPI a5 tiveram SHA256 verificado localmente; isso não equivale a executar todos os wheels. Docker e CI usam uv sync --locked. Aceitação Linux/container a5 permanece pendente.
