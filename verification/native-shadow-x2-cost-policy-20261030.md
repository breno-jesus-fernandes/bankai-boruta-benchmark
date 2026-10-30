# Native-shadow 2× em c7a.8xlarge: política de preço — 30/10/2026

A rodada 2× do protocolo `native-shadow-max40-v1` usa uma única `c7a.8xlarge`: AMD EPYC, 32 vCPUs = 32 núcleos físicos (C7a não tem SMT), 64 GiB e 32 threads. A cota EC2 Standard On-Demand em us-east-1 é de 32 vCPUs, então esse host ocupa a cota inteira. O runner recusa iniciar se houver qualquer instância EC2 ativa.

## Tarifas consultadas em 30/10/2026 (AWS Price List API, us-east-1, Linux, compartilhada)

- `c7a.8xlarge`: **US$1,64224/h**. Para referência, a `c7a.4xlarge` custa US$0,82112/h.
- EBS gp3 de 100 GB: US$0,01096/h. IPv4 pública: US$0,005/h.
- Custo conhecido: US$1,65820/h. Com 20% de contingência, **US$1,99/h**.
- PTAX de venda do BCB em 30/10: R$5,4212/US$, ou cerca de R$10,79 por hora-host.

## Reserva

O ledger suplementar `bankai-budget/supplemental-150-usd.json` tinha US$49,50 alocados em 12 lançamentos. Restavam **US$100,50**. A c7a.8xlarge reserva US$3,00 por hora armada (`SUPPLEMENTAL_HOUR_USD_8XL`), o dobro do slot da 4xlarge e acima do custo estimado. O ledger em BRL não é usado. A política em `budget.py` vale até 06/11/2026.

## Dados 2× (gerados em macOS, seed 42, fora do cronômetro)

| Perfil | Treino | Relevantes | Geração | RSS máx. |
|---|---|---:|---:|---:|
| Cibersegurança | 800.000 × 300 | 60 | 11,5 s | 2,4 GiB |
| Bioinformática | 100.000 × 4.000 | 30 | 98,8 s | 3,5 GiB |

O piloto gera os dados uma vez por seed e cada worker os carrega inteiros, sem mmap, antes do baseline de RSS. Os bytes são idênticos aos da geração direta: o `data_sha256` do Industrial seed 42 1× confere com o artefato a12 publicado.

## Etapas e estimativas

| Etapa | Escopo | Horas armadas | Reserva |
|---|---|---:|---:|
| Calibração | 4 perfis 2×, seed 42, 1 repetição | 2 | US$6 |
| Campanha | 4 perfis 2×, 5 seeds × 5 repetições, em lançamentos por perfil | a definir pela calibração (~14 h estimadas) | ~US$45 |
| CIC-IDS2017 | 5 seeds, 1 repetição, 32 threads | 2 | US$6 |

Cada lançamento exige aprovação explícita, com shutdown AWS armado antes da reserva.
