# Verificação do protocolo v2

A evidência local está em [verification/v2-local/VALIDATION.md](verification/v2-local/VALIDATION.md). O smoke valida funcionamento e retomada; não comprova desempenho, recall em escala real nem comportamento de memória no Linux.

```sh
uv sync --locked
uv run pytest -q
uv run python scripts/verify_smoke.py
uv run python scripts/verify_campaign_archive.py verification/campaign-20261017
```

A atestação `src/bankai_benchmark/release-verification.json` distingue hashes públicos, controles locais e aceitação Linux por protocolo. O aceite Linux r4 é histórico e não valida r5. O protocolo r5 passou no GitHub Actions, incluindo a imagem construída, os 16 casos, VmHWM, topologia/afinidade e caminho Rust dos dois métodos Bankai. [Verificação a4 original](docs/history/a4-20261017/VERIFICATION.md).

Antes da campanha full, verificar no host AMD c7a.4xlarge 16 núcleos físicos, uma thread por núcleo e nested affinity 1/2/4/8/16. A aceitação Linux genérica não substitui essa verificação do host de benchmark. Publicar imagem somente por digest, com revisão e evidência CI da a6.

Validação CloudFormation local por testes estruturais está incluída. Schema completo, segurança/compliance por ferramentas e validação de serviço AWS têm status separado no relatório; aprovação nos testes Python não significa aceitação AWS. Nenhuma chamada de validação/deploy AWS é necessária nesta etapa.
