# Bankai Boruta benchmark v2

Protocolo `paper-v2-a5-amd16`, gerador `2.0.0`, Bankai Boruta **0.1.0a5** e BankaiRF **0.1.0a15**. Esta revisão entrega implementação e validação local. Ainda não há resultados de desempenho v2 ou evidência de melhora de recall em escala real.

Quatro métodos: `bankai_classic_native`, `bankai_classic_adapter`, `borutapy_sklearn_et` e `borutapy_lightgbm_rf`. O clássico usa `perc=100`, alpha 0,05, duas etapas estatísticas e sem early stopping. Orçamentos, profundidade, bins, bootstrap e amostragem de cada backend permanecem como na a4; ExtraTrees não usa bootstrap, BankaiRF usa, e LightGBM RF usa subsample 0,8. Greedy pertence somente ao histórico.

| Perfil | Treino N | Teste N | P | Árvores | Profundidade | Iterações máximas | Prevalência | SNR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Industrial | 200.000 | 50.000 | 500 | 100 | 6 | 50 | 0,5 | 1 |
| Crédito | 300.000 | 75.000 | 300 | 100 | 6 | 50 | 0,2 | 1 |
| Bioinformática | 50.000 | 12.500 | 2.000 | 150 | 8 | 60 | 0,5 | 1 |
| Cibersegurança | 400.000 | 100.000 | 150 | 100 | 6 | 40 | 0,1 | 1 |

Todos usam 63 bins. A amostragem é `sqrt`, exceto Bioinformática, que usa 0,15. O teste tem 25% das linhas do treino. O smoke reduz para 400/100 linhas, pelo menos 40 colunas (60 em Cibersegurança), oito árvores, profundidade três e quatro iterações. Não serve para comparar desempenho ou calibrar recall.

Os termos padronizados recebem pesos fixos: Industrial `[1,1,0.25,0.25,0.02,0.02]`; Crédito sete termos de peso 1, quatro de 0,25 e três de 0,02; Cibersegurança repete, nos grupos step/periódico/esparso, dez pesos 1, seis 0,25 e quatro 0,02. Bioinformática conserva dez termos correlacionados de peso 0,35 e dez termos de peso 1, cada um `standardize(tanh(2*u*v)+0.35*(u+v)/sqrt(2))`. Seu subtipo é `interaction_marginal_signal`, distinto da interação pura histórica.

A verdade conhecida conserva sinais e redundâncias: 12/20/30/60 features relevantes. Pesos, índices dos termos, permutação de colunas e grupos de intensidade ficam nos metadados. Grupos podem se sobrepor: Industrial x0 participa de termo forte e interação fraca. As redundâncias herdam a intensidade de sua origem. Bioinformática classifica 0,35 como médio. O recall global continua principal; recall por intensidade e subtipo são complementares.

A calibração sintética é conjunta treino/teste, determinística por seed, com termos e ruído padronizados, seguida de split estratificado. Nenhum modelo é ajustado no teste. Cache inclui versão/hash do gerador e perfil. As mudanças são iguais para todos os métodos. Redução da saturação e recuperação de efeitos marginais são hipóteses para uma campanha futura.

## Uso local

```sh
uv sync --locked
uv run pytest -q
uv run python scripts/verify_smoke.py
# Qualquer perfil pode ser selecionado; use diretórios próprios para smokes parciais.
uv run python scripts/verify_smoke.py --dataset bioinformatica --results /tmp/bio-v2/results --output /tmp/bio-v2/report
```

O smoke usa diretórios exclusivos sob `verification/v2-local`. O comando verifica sucesso, relatórios provisórios e retomada byte a byte. A identidade do protocolo, dependências, fonte e configuração fazem parte dos manifests; manifest incompatível exige outro ID. Agregação recusa mistura de protocolos/fontes/dependências.

## Medição e métricas

Cada fit roda em processo novo. Carregamento, preparação e avaliação downstream ficam fora do cronômetro e da coleta de memória do seletor. RSS é amostrado a cada 5 ms; Linux também registra VmHWM e tentativa de reset antes do fit. Quando o reset falha, o high-water mark é explicitamente de toda a vida do processo. Delta de pico subtrai o baseline. Buffers explícitos e bytes copiados da a5 são diagnósticos separados de RSS; valores numéricos recebem mediana/IQR nos resumos.

Linux lê package/core IDs no sysfs e cruza com a afinidade permitida. Seleciona um processador lógico por núcleo, em conjuntos aninhados de 1/2/4/8/16. Recusa topologia ausente ou núcleos insuficientes e confere afinidade efetiva. Registra fabricante, modelo, topologia permitida, CPUs selecionadas e afinidade. macOS smoke declara essas verificações indisponíveis. OpenMP, Rayon e `n_jobs` seguem o número solicitado; BLAS, NumExpr e Accelerate usam uma thread.

Precisão, recall, F1, FDR, falsos positivos trap e seleções tentativas são reportados. Downstream usa ExtraTrees com 200 árvores, max_features sqrt, class_weight balanced, somente features confirmadas; registra AUC, accuracy, balanced accuracy e F1. Oracle e todas as features são referências em processos próprios. Medianas e quartis usam quantile linear; falhas nunca viram observações zero. Smoke ou campanhas incompletas não geram placeholders finais.

## Campanha futura AMD

Alvo: `c7a.4xlarge`, AMD EPYC, 16 núcleos físicos, uma thread por núcleo, 32 GiB ([especificação AWS](https://docs.aws.amazon.com/ec2/latest/instancetypes/co.html)). ECS sobre EC2, uma tarefa por host, reserva 16 CPUs e 28 GiB. `MACHINE` em `config.py` centraliza a identidade; templates e placement usam esse alvo, capacidade desejada zero nos planos offline.

Qualidade: quatro perfis × quatro métodos × cinco seeds (42–46) × 16 núcleos = 80 fits. Escala: Industrial × quatro métodos × cinco seeds × 1/2/4/8/16 núcleos = 100 fits independentes. Dois warmups por célula usam seeds 900001/900002. Não reutilizar observações da qualidade ou da a4 na escala v2.

```sh
# Executar somente depois da aceitação Linux/container e aprovação da campanha futura.
uv run bankai-benchmark full --suite quality --experiment paper-v2-a5-amd16 --results results-v2
uv run bankai-benchmark full --suite scaling --experiment paper-v2-a5-amd16 --results results-v2
uv run bankai-aggregate --results results-v2 --output reports-v2
uv run python scripts/analyze_campaign.py --quality results-v2/paper-v2-a5-amd16-quality --scaling results-v2/paper-v2-a5-amd16-scaling --output reports-v2/analysis
```

O gerador de relatórios v2 usa baseline de uma CPU e apenas observações novas. Consulte [validação](VERIFICATION.md), [infraestrutura](deployment/README.md), [orçamento](BUDGET.md) e [dependências/licenças](DEPENDENCIES.md).

## Histórico preservado

[README a4 de 17/10/2026](docs/history/a4-20261017/README.md) contém resultados e instruções daquela campanha, não defaults v2. Resultados sob `verification/campaign-20261017`, `verification/pilot-20261017`, `results-public-a4*` e relatórios existentes não foram recalculados. Checksums históricos continuam válidos. `config-paper-v1.json` preserva o mapeamento antigo; leitores usam o manifest para escolher o protocolo. `scaling48.py` aceita somente arquivos históricos e recusa execução v2; o controlador antigo não é o caminho da nova escala.
