# Verificação do protocolo v2

A evidência local está em [verification/v2-local/VALIDATION.md](verification/v2-local/VALIDATION.md). O smoke valida funcionamento e retomada; não comprova desempenho, recall em escala real nem comportamento de memória no Linux.

```sh
uv sync --locked
uv run pytest -q
uv run python scripts/verify_smoke.py
uv run python scripts/verify_campaign_archive.py verification/campaign-20261017
```

A atestação `src/bankai_benchmark/release-verification.json` distingue hashes públicos, controles locais e aceitação Linux por protocolo. O aceite Linux r4 é histórico e não valida r5. O protocolo r5 passou no GitHub Actions e no smoke ECS AMD, incluindo 16 casos, VmHWM, topologia/afinidade e caminho Rust dos dois métodos Bankai. [Evidência do smoke ECS r5](verification/v2-r5-ecs-smoke-20261018.md). [Verificação a4 original](docs/history/a4-20261017/VERIFICATION.md).

Antes da campanha full, a topologia do host AMD c7a.4xlarge foi verificada no smoke ECS: 16 núcleos físicos, uma thread por núcleo e afinidade observada. A campanha de escala ainda precisa exercitar os conjuntos aninhados de 4/8/16. A imagem foi publicada somente por digest, com evidência CI da a6.

Validação CloudFormation local por testes estruturais está incluída. Schema completo, segurança/compliance por ferramentas e validação de serviço AWS têm status separado no relatório; aprovação nos testes Python não significa aceitação AWS. Nenhuma chamada de validação/deploy AWS é necessária nesta etapa.


## Candidato exato a7 (separado da referência a6)

A otimização a7/RF a16 tem [protocolo, diagnósticos, reprodução e critérios próprios](docs/exact-session-a7.md). O caminho novo permanece optativo, sem substituir pins, imagens, observações ou resultados históricos a6/a15. A validação AMD 1/4/16 workers e Industrial completo está pendente; esta atualização não alocou AWS nem alterou reservas.
