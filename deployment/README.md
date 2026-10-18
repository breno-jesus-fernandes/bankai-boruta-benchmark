# Infraestrutura v2 — somente offline nesta etapa

`config.MACHINE`: c7a.4xlarge AMD, 16 núcleos físicos, ThreadsPerCore=1, 32 GiB. LaunchTemplate fixa 16/1; ECS reserva 16384 CPU units e 28672 MiB por tarefa, placement distinctInstance e tipo c7a. Uma tarefa por host. Fleet inicia MinSize=0, DesiredCapacity=0, MaxSize=1. Subnets e security groups continuam fornecidos pelo operador.

```sh
uv run bankai-aws plan --help
uv run pytest -q tests/test_aws.py tests/test_topology.py
make docker-smoke
```

O último comando exige Docker/Linux e está pendente nesta máquina. Gere um novo plano com `bankai-aws plan` e os argumentos de rede/bucket/imagem próprios da futura campanha; não reutilize ARNs, digest ou estado a4. `pilot-plan.json` é um exemplo offline com identificadores fictícios e zero capacidade, não um plano pronto para deploy.

Qualidade full: 60 fits (cinco seeds, 16 núcleos). Escala Industrial full: 75 fits novos (1/2/4/8/16 núcleos). Usar o orchestrator padrão; `scripts/scaling48.py` é leitor/controlador histórico, bloqueado para o v2. Os controladores operacionais usam placement AMD, mas ledger, shutdown, orçamento e aceitação do host devem ser revisados na etapa futura.

Publicação: Dockerfile instala a5 pelo lock; CI executa suíte e aceitação Linux antes de publicar. Nesta etapa nenhum workflow foi disparado, nenhuma imagem foi publicada e nenhum recurso AWS foi iniciado. O digest antigo continua somente no histórico. [Runbook a4](../docs/history/a4-20261017/deployment-README.md).
