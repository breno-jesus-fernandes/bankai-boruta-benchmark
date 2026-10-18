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

O protocolo `paper-v2-a6-amd16-r5` requer bankai-boruta==0.1.0a6 e bankai-random-forest==0.1.0a15. A a6 está publicada no PyPI; `uv.lock` fixa essa versão e os SHA256 de todos os seis artefatos foram verificados por download. As versões resolvidas dos outros pacotes permaneceram iguais às do lock anterior. A aceitação Linux/container r5 passou no GitHub Actions; a validação da máquina AMD dedicada ainda depende do smoke ECS.
