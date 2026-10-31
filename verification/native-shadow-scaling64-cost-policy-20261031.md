# Escala 8/16/32/64 threads na Industrial 2×: preço e orçamento (31/10/2026)

- **Cota:** a cota EC2 On-Demand Standard em us-east-1 subiu de 32 para 64 vCPUs (caso 179340825100945), o que permite uma c7a.16xlarge (64 núcleos AMD físicos, SMT desligado, 128 GiB) por vez.
- **Preço:** US$3,28448/h on-demand em 31/10/2026 (AWS Pricing API, Linux, us-east-1); cerca de US$3,97/h com EBS, IPv4 e 20% de contingência. A reserva usa US$6,00 por hora armada (`SUPPLEMENTAL_HOUR_USD_16XL`), o dobro da c7a.8xlarge.
- **Orçamento:** o ledger suplementar tinha US$136,50 alocados de US$150. Aprovado em 31/10/2026, o teto sobe para **US$165**; a primeira reserva grava o aumento em `raises` dentro do próprio ledger. A política em `budget.py` continua válida até 06/11/2026.

## Plano

Um lançamento: Industrial 2× (400k × 1.000), os quatro métodos, seeds 42–46, uma repetição, com o piloto rodando 8, 16, 32 e 64 threads em sequência no mesmo host, e a AUC no próprio container depois da última contagem.

| Threads | Estimativa por seed (4 métodos) |
|---:|---:|
| 8 | ~12 min |
| 16 | ~8 min |
| 32 | ~6 min (medido na campanha 2×) |
| 64 | ~5 min |

Cerca de 2,6 h de tarefa mais a AUC: **4 h armadas, US$24 reservados**, custo real estimado em ~US$12.

## Execução

Lançado em 31/10/2026 com a imagem `sha256:610ec1cb…1f61480` (stack `bankai-ns-scaling64`, estado `native-shadow-scaling64-amd64-20261031.json`). A tarefa rodou das 18:07Z às 20:33Z: 8 threads levaram 46 min, 16 threads 35 min, 32 threads 31 min e 64 threads 32 min, incluindo a AUC. Cerca de 2,5 h de host, ~US$8–9 on demand. O runner drenou a frota e a stack foi apagada. O ledger suplementar fica com US$160,50 reservados de US$165.
