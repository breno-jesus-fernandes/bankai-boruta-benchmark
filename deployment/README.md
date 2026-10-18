# Infraestrutura v2

`config.MACHINE`: c7a.4xlarge AMD, 16 núcleos físicos, ThreadsPerCore=1, 32 GiB. LaunchTemplate fixa 16/1; ECS reserva 16384 CPU units e 28672 MiB por tarefa, placement distinctInstance e tipo c7a. Uma tarefa por host. Fleet inicia MinSize=0, DesiredCapacity=0, MaxSize=1. Subnets e security groups continuam fornecidos pelo operador.

```sh
uv run bankai-aws plan --help
uv run pytest -q tests/test_aws.py tests/test_topology.py
make docker-smoke
```

O workflow Linux/container r4 passou e publicou o digest imutável registrado em `src/bankai_benchmark/release-verification.json`; Docker não está instalado neste Mac, então a validação ocorreu no GitHub Actions. Gere planos com `bankai-aws plan` e os argumentos de rede/bucket/imagem; o modo smoke deve ser explícito com `--mode smoke`. `pilot-plan.json` é um exemplo offline com identificadores fictícios e zero capacidade, não um plano pronto para deploy.

Qualidade full: 60 fits (cinco seeds, 16 núcleos). Escala Industrial full: 75 fits novos (1/2/4/8/16 núcleos). Usar o orchestrator padrão; `scripts/scaling48.py` é leitor/controlador histórico, bloqueado para o v2. Os controladores operacionais usam placement AMD, mas ledger, shutdown, orçamento e aceitação do host devem ser revisados na etapa futura.

Publicação: Dockerfile instala a5 pelo lock; CI executa suíte e aceitação Linux antes de publicar. O digest atual é r4; o smoke ECS será executado com uma reserva de R$20, uma instância e shutdown automático de uma hora. [Runbook a4](../docs/history/a4-20261017/deployment-README.md).
