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

O protocolo `paper-v2-a6-amd16-r5` requer bankai-boruta==0.1.0a6 e bankai-random-forest==0.1.0a15. A a6 está publicada no PyPI; `uv.lock` fixa essa versão e os SHA256 de todos os seis artefatos foram verificados por download. As versões resolvidas dos outros pacotes permaneceram iguais às do lock anterior. A aceitação Linux/container passou no GitHub Actions, e o smoke ECS confirmou a execução no host AMD dedicado.


## Candidato exato a7 (separado da referência a6)

A otimização a7/RF a16 tem [protocolo, diagnósticos, reprodução e critérios próprios](docs/exact-session-a7.md). O caminho novo permanece optativo, sem substituir pins, imagens, observações ou resultados históricos a6/a15. A validação AMD 1/4/16 workers e Industrial completo está pendente; esta atualização não alocou AWS nem alterou reservas.
