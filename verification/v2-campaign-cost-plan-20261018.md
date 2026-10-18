# Planejamento de custo v2 — 18/10/2026

> Snapshot preparado antes da autorização do ledger BRL400. O estado atualizado do orçamento e a calibração aprovada estão em [BUDGET.md](../BUDGET.md); os cenários e tarifas abaixo continuam como referência datada, não como cobrança ou autorização vigente.

Este é um cenário de custo, não uma autorização de execução nem uma previsão de duração. O smoke ECS terminou corretamente, mas usou apenas 400 linhas por perfil; seus 39 segundos não podem ser extrapolados para os dados completos.

## Escopo de trabalho

O protocolo full contém 80 fits medidos de qualidade e 100 de escalabilidade. Os grids completos definem ainda 32 warmups de qualidade, 40 warmups de escalabilidade e 25 execuções de referência downstream: **277 execuções de seletor/referência** ao todo. A contagem foi obtida de `trial_grid()` e da regra atual de warmups em `orchestrator.py`. Cada tarefa usa um host; o custo depende da soma de horas faturáveis de todos os hosts, não apenas do tempo de parede se houver paralelismo.

## Tarifas consultadas

- EC2 Linux On-Demand, tenancy compartilhada, `c7a.4xlarge`, `us-east-1`: **US$0,82112 por hora-host**, consultado no AWS Price List API em 18/10/2026.
- EBS GP3 `us-east-1`: US$0,08 por GB-mês. O template provisiona 100 GB e remove o volume ao terminar a instância. Rateio usado: 730 horas/mês.
- IPv4 pública: US$0,005 por endereço-hora. A sub-rede da stack tem `MapPublicIpOnLaunch=true`.
- Câmbio: PTAX venda do BCB em 16/10/2026: **R$5,0826/US$**; 18/10 caiu em domingo.
- Para cenários, foi acrescentada uma contingência de 20% ao custo conhecido por hora-host para partidas/esperas, logs e pequenos encargos incidentais. É uma hipótese de planejamento, não uma tarifa AWS nem substitui impostos, spread cambial ou créditos particulares da conta.

O custo conhecido é US$0,83708 por hora-host antes da contingência, equivalente a aproximadamente R$5,1054 por hora-host com a contingência e a PTAX indicadas.

| Horas-host totais | USD com contingência | BRL com PTAX e contingência |
|---:|---:|---:|
| 8 | US$8,04 | R$40,84 |
| 16 | US$16,07 | R$81,69 |
| 24 | US$24,11 | R$122,53 |
| 48 | US$48,22 | R$245,06 |
| 72 | US$72,32 | R$367,59 |

Os valores foram calculados por script decimal com as tarifas acima. O smoke gravou 21 objetos totalizando 171.418 bytes no S3; esse volume é pequeno comparado à computação, mas retenção final e CloudWatch devem entrar na estimativa aprovada. Não foram incluídos impostos, tráfego fora da região, NAT Gateway, snapshots persistentes ou custos preexistentes da conta.

## Bloqueios antes de uma campanha

1. Duração real continua desconhecida. Executar um calibration run representativo em tamanho full, medir soma de horas-host e RSS/diagnósticos, e usar essa observação para fixar o teto da campanha.
2. O ledger atual chegou a nove reservas de R$20 (R$180 alocados), deixando somente a reserva protegida de R$40 dentro do limite de R$220. Não há saldo autorizável para novos lançamentos nele.
3. O guard atual foi desenhado para um piloto de até uma hora. Uma campanha de 277 execuções precisa de um controller e de deadlines de shutdown adequados a múltiplas horas, com reserva de custo baseada em horas-host e encerramento validado.
4. A política de preço/câmbio expira em 24/10/2026. Consultar novamente EC2, EBS, IPv4, FX e custos incidentais imediatamente antes de aprovar campanha ou calibration run.
5. A stack smoke continua provisionada, mas seu ASG está em min/max/desejado zero e sem instâncias. Não usar esse estado como capacidade pronta para campanha; revisar drift e os limites de execução primeiro.

O próximo passo recomendado é preparar um controller full com teto explícito em horas-host/custo e shutdown verificado, então pedir aprovação de um calibration run de tamanho real com limite independente. Campanha de qualidade e escalabilidade só deve ser orçada depois desse runtime medido.

## Fontes

- AWS [EC2 On-Demand pricing](https://aws.amazon.com/ec2/pricing/on-demand/) e [C7a](https://aws.amazon.com/ec2/instance-types/c7a/); taxa unitária consultada via AWS Price List API para `AmazonEC2` (`instanceType=c7a.4xlarge`, Linux, shared, `US East (N. Virginia)`).
- AWS [guia para encontrar preços no Price List](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/finding-prices-in-service-price-list-files.html).
- AWS [preço de endereços IPv4 públicos](https://aws.amazon.com/vpc/pricing/) e [preços do EBS](https://aws.amazon.com/ebs/pricing/); o GP3 foi consultado via Price List API em 18/10/2026.
- BCB [série diária PTAX USD](https://dadosabertos.bcb.gov.br/dataset/dolar-americano-usd-todos-os-boletins-diarios), consulta de venda referente a 16/10/2026.
