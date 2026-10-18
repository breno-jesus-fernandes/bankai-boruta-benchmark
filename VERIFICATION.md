# Verificação do protocolo v2

A evidência local está em [verification/v2-local/VALIDATION.md](verification/v2-local/VALIDATION.md). O smoke valida funcionamento e retomada; não comprova desempenho, recall em escala real nem comportamento de memória no Linux.

```sh
uv sync --locked
uv run pytest -q
uv run python scripts/verify_smoke.py
uv run python scripts/verify_campaign_archive.py verification/campaign-20261017
```

A atestação `src/bankai_benchmark/release-verification.json` distingue hashes públicos, controles locais e aceitação Linux por protocolo. O aceite Linux r4 é histórico e não valida r5. [Verificação a4 original](docs/history/a4-20261017/VERIFICATION.md).

Para aceitar Linux/container r5: executar `make docker-smoke` em host Linux com sysfs legível e pelo menos um núcleo permitido. O script exige 16 smokes, VmHWM, afinidade física, thread BLAS única e caminho Rust do seletor nos dois métodos Bankai. Antes da campanha full, verificar também 16 núcleos físicos AMD, uma thread por núcleo e nested affinity 1/2/4/8/16 no host real. Publicar imagem somente por digest, com revisão e evidência CI da a6.

Validação CloudFormation local por testes estruturais está incluída. Schema completo, segurança/compliance por ferramentas e validação de serviço AWS têm status separado no relatório; aprovação nos testes Python não significa aceitação AWS. Nenhuma chamada de validação/deploy AWS é necessária nesta etapa.
