# Infraestrutura v2

`config.MACHINE`: c7a.4xlarge AMD, 16 núcleos físicos, ThreadsPerCore=1, 32 GiB. LaunchTemplate fixa 16/1; ECS reserva 16384 CPU units e 28672 MiB por tarefa, placement distinctInstance e tipo c7a. Uma tarefa por host. Fleet inicia MinSize=0, DesiredCapacity=0, MaxSize=1. Subnets e security groups continuam fornecidos pelo operador.

```sh
uv run bankai-aws plan --help
uv run pytest -q tests/test_aws.py tests/test_topology.py
make docker-smoke
```

O workflow Linux/container r5 passou no GitHub Actions. Isso valida o container Linux, mas não a topologia do host AMD dedicado. Gere planos com `bankai-aws plan` e os argumentos de rede/bucket/imagem; o modo smoke deve ser explícito com `--mode smoke`. `pilot-plan.json` é um exemplo offline com identificadores fictícios e zero capacidade, não um plano pronto para deploy.

Qualidade full: 80 fits (cinco seeds, 16 núcleos). Escala Industrial full: 60 fits novos (4/8/16 núcleos, baseline de quatro). Usar o orchestrator padrão; `scripts/scaling48.py` é leitor/controlador histórico, bloqueado para o v2. Os controladores operacionais usam placement AMD, mas ledger, shutdown, orçamento e aceitação do host devem ser revisados na etapa futura.

Publicação: a6 já está publicada e o lock instala `bankai-boruta==0.1.0a6`. CI executa suíte e aceitação Linux antes de publicar a imagem. É necessário publicar um novo digest r5 antes do smoke ECS. A reserva de R$20 previamente aprovada será reaproveitada sem elevar o teto, com uma instância e shutdown automático no prazo original. [Runbook a4](../docs/history/a4-20261017/deployment-README.md).
