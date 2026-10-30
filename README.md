# Bankai Boruta benchmark

Benchmark reproduzível do [Bankai Boruta](https://github.com/breno-jesus-fernandes/bankai-boruta) contra o BorutaPy. Os resultados atuais usam o protocolo `native-shadow-max40-v1` com o **Bankai Boruta 0.1.0a12** e o **BankaiRF 0.1.0a20**, publicados no PyPI. O protocolo v2 (a6) e as campanhas anteriores continuam documentados mais abaixo.

## Resultados atuais (0.1.0a12)

- **Máquina:** uma EC2 c7a.4xlarge (16 núcleos AMD físicos, SMT desligado, 32 GiB) no ECS, 16 threads.
- **Métodos:**
  - Bankai exato: Extra Trees do BankaiRF com cortes nos valores originais;
  - Bankai bins: Extra Trees do BankaiRF com 63 bins;
  - BP/E: BorutaPy 0.4.3 + `ExtraTreesClassifier` do scikit-learn 1.9.1;
  - BP/L: BorutaPy + LightGBM em modo random forest (63 bins, subamostragem 0,8).
- **Configuração comum:** árvores, profundidade e fração de features de cada perfil, bootstrap, `perc=100`, `alpha=0.05`, `two_step=True`, no máximo 40 rodadas com parada natural, float32 e seeds 42–46.
- **Medição:**
  - cada fit roda num processo novo, depois de gerar os dados;
  - o tempo cobre só o `fit`;
  - a memória é o pico de RSS acima do que os dados já ocupam, amostrado de fora a cada 5 ms;
  - a AUC vem de um ExtraTrees de 200 árvores treinado só com as features confirmadas e avaliado no teste.

### Perfis sintéticos

Mediana sobre cinco seeds, cada uma a mediana de cinco repetições ([detalhes](verification/native-shadow-synthetic-a12-r5-amd-20261023/README.md)).

| Perfil (treino n × p, relevantes) | Método | Tempo (s) | RSS (MiB) | Precisão | Recall | AUC |
|---|---|---:|---:|---:|---:|---:|
| Industrial 200k × 500 (12) | Bankai exato | **9,2** | 931 | 1,00 | 0,67 | 0,837 |
| | Bankai bins | 10,8 | **456** | 1,00 | 0,67 | 0,837 |
| | BP/E | 37,1 | 1.816 | 1,00 | 0,67 | 0,837 |
| | BP/L | 75,1 | 4.865 | 1,00 | 0,67 | 0,837 |
| Crédito 300k × 300 (20) | Bankai exato | **9,5** | 929 | 1,00 | 0,85 | 0,852 |
| | Bankai bins | 10,9 | **506** | 1,00 | 0,85 | 0,852 |
| | BP/E | 46,2 | 1.805 | 1,00 | 0,85 | 0,852 |
| | BP/L | 52,7 | 3.429 | 1,00 | 0,85 | 0,852 |
| Cibersegurança 400k × 150 (60) | Bankai exato | 24,5 | 760 | 1,00 | 0,67 | 0,837 |
| | Bankai bins | **23,5** | **476** | 1,00 | 0,62 | 0,838 |
| | BP/E | 110,4 | 1.455 | 1,00 | 0,65 | 0,836 |
| | BP/L | 79,9 | 1.877 | 1,00 | 0,55 | 0,837 |
| Bioinformática 50k × 2000 (30) | Bankai exato | 85,7 | 853 | 1,00 | 1,00 | 0,750 |
| | Bankai bins | **71,1** | **388** | 1,00 | 1,00 | 0,750 |
| | BP/E | 145,1 | 1.608 | 1,00 | 1,00 | 0,750 |
| | BP/L | 130,0 | 5.823 | 1,00 | 0,80 | 0,734 |

- **Tempo e memória:** os dois modos do Bankai foram mais rápidos e usaram menos memória que BP/E e BP/L em todas as 20 combinações de perfil e seed.
  - Frente ao BP/E, o Bankai exato gastou em mediana 76% menos tempo (de 41% a 87%) e 48% menos memória.
  - Frente ao BP/E, o modo com bins gastou 76% menos tempo e 73% menos memória.
- **Seleção:**
  - Nenhum método confirmou feature irrelevante.
  - Em Industrial, Crédito e Bioinformática, Bankai exato, Bankai bins e BP/E confirmaram os mesmos conjuntos em todas as seeds.
  - Na Cibersegurança, todos chegaram às 40 rodadas, e os conjuntos diferem em uma a quatro features limítrofes por seed.
  - O BP/L perdeu até 12 das 30 relevantes na Bioinformática.
- **Contra o 0.1.0a8:** o Bankai exato ficou de 1,6 a 2,5 vezes mais rápido e usa de 13% a 46% menos memória, com seleções idênticas em todos os perfis, seeds e repetições.

### CIC-IDS2017 (dados reais)

Base de treino com 1.748.586 linhas e 78 colunas em float32 (`scripts/prepare_cicids2017.py`), com a configuração do perfil Cibersegurança e uma repetição por seed ([detalhes](verification/native-shadow-cicids2017-a12-amd-20261023/README.md)).

| Método | Tempo (s) | RSS (MiB) | s/rodada | Rodadas | Confirmadas | AUC |
|---|---:|---:|---:|---:|---:|---:|
| Bankai exato | **39,8** | 2.140 | 3,29 | 12 | 68 | 0,99872 |
| Bankai bins | 129,2 | **1.517** | 3,23 | 40 | 66 | 0,99874 |
| BP/E | 130,8 | 4.146 | 11,0 | 12 | 68 | 0,99872 |
| BP/L | 280,3 | 2.736 | 7,02 | 40 | 66 | 0,99874 |

O Bankai exato confirmou as mesmas 68 features que o BP/E em todas as seeds, 3,3 vezes mais rápido e com cerca de metade da memória. Com todas as 78 features, a AUC é 0,99871.

### Reproduzir

```sh
uv sync --locked
# O lock fixa a a6 do protocolo v2; instale as versões medidas por cima dele.
uv pip install bankai-boruta==0.1.0a12 bankai-random-forest==0.1.0a20
# Um perfil e uma seed localmente (gera os dados, roda os quatro métodos e grava o JSON)
BANKAI_BENCHMARK_SRC=src uv run --no-sync python scripts/native_shadow_pilot.py --datasets industrial --seeds 42 --repeats 1 --threads 8 --output-dir /tmp/ns
uv run --no-sync python scripts/native_shadow_summary.py /tmp/ns
uv run --no-sync python scripts/native_shadow_auc.py /tmp/ns /tmp/ns/auc.json
# CIC-IDS2017: baixa e prepara os CSVs com hash conferido
uv run --no-sync python scripts/prepare_cicids2017.py /tmp/cicids2017
```

### Próxima rodada: dados 2× em 32 threads

Os quatro perfis sintéticos com N e P dobrados (`--scale 2`: Industrial 400k × 1.000, Crédito 600k × 600, Bioinformática 100k × 4.000, Cibersegurança 800k × 300, com as mesmas features relevantes) numa `c7a.8xlarge` (32 núcleos AMD físicos, 64 GiB). Mesmos métodos, versões (a12/a20) e protocolo; o CIC-IDS2017 roda de novo em 32 threads, sem escala. Os artefatos têm sufixo `-x2`. Ainda não há resultados; custos e etapas em [política de preço 2×](verification/native-shadow-x2-cost-policy-20261030.md).

```sh
BANKAI_BENCHMARK_SRC=src uv run --no-sync python scripts/native_shadow_pilot.py --datasets industrial --seeds 42 --repeats 1 --threads 8 --scale 2 --output-dir /tmp/ns2
# Na AWS, com a imagem native-shadow publicada (a12/a20):
uv run python scripts/run_native_shadow_aws.py --image <uri@sha256> --subnets <subnet> --security-groups <sg> \
  --instance c7a.8xlarge --scale 2 --datasets industrial credito bioinformatica ciberseguranca --seeds 42 --repeats 1 --hours 2 \
  --stack bankai-native-shadow-x2-cal --state verification/native-shadow-x2-calibration.json
```

Na AWS, `scripts/run_candidate_probe_aws.py` sobe a stack, roda wheels Linux escolhidas (`--wheel`, `--extra-wheel`) sobre a imagem publicada e apaga a stack no fim. O desligamento é armado antes de qualquer capacidade, e as horas são reservadas no ledger de [orçamento](BUDGET.md).

## Protocolo v2 (a6, histórico)

Protocolo `paper-v2-a6-amd16-r5`, gerador `2.0.0`, Bankai Boruta **0.1.0a6** e BankaiRF **0.1.0a15**. A a6 está publicada no PyPI; o lock foi regenerado e os seis artefatos públicos tiveram SHA256 conferido. A aceitação Linux/container passou no GitHub Actions, e o smoke ECS AMD passou com 16/16 trials. Ainda não há resultados de desempenho r5 ou evidência de melhora de recall em escala real.

Quatro métodos: `bankai_native_extra_tree` usa BankaiRF ExtraTrees exato; `bankai_native_extra_tree_binned` usa BankaiRF ExtraTrees com bins e o caminho acelerado de sombras virtuais do BankaiBoruta; os outros são `borutapy_sklearn_et` e `borutapy_lightgbm_rf`. Na a6, ambos os métodos Bankai usam Rust no seletor e na floresta; o caminho exato nativo exige entrada float32, como nos geradores deste benchmark. Os três métodos ExtraTrees usam bootstrap; LightGBM RF usa subsample 0,8. BankaiBoruta e BorutaPy usam `early_stopping=True`, paciência de 100 iterações (`n_iter_no_change=100`) e limite máximo de 120 iterações. No smoke, o limite é reduzido para quatro, então a parada antecipada não é alcançável. Greedy e o adaptador pertencem somente aos leitores históricos.

| Perfil | Treino N | Teste N | P | Árvores | Profundidade | Iterações máximas | Prevalência | SNR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Industrial | 200.000 | 50.000 | 500 | 100 | 6 | 120 | 0,5 | 1 |
| Crédito | 300.000 | 75.000 | 300 | 100 | 6 | 120 | 0,2 | 1 |
| Bioinformática | 50.000 | 12.500 | 2.000 | 150 | 8 | 120 | 0,5 | 1 |
| Cibersegurança | 400.000 | 100.000 | 150 | 100 | 6 | 120 | 0,1 | 1 |

Somente o método Bankai binned usa 63 bins; os métodos ExtraTrees exatos não usam bins. A amostragem é `sqrt`, exceto Bioinformática, que usa 0,15. O teste tem 25% das linhas do treino. O smoke reduz para 400/100 linhas, pelo menos 40 colunas (60 em Cibersegurança), oito árvores, profundidade três e quatro iterações. Não serve para comparar desempenho ou calibrar recall.

Os termos padronizados recebem pesos fixos: Industrial `[1,1,0.25,0.25,0.02,0.02]`; Crédito sete termos de peso 1, quatro de 0,25 e três de 0,02; Cibersegurança repete, nos grupos step/periódico/esparso, dez pesos 1, seis 0,25 e quatro 0,02. Bioinformática conserva dez termos correlacionados de peso 0,35 e dez termos de peso 1, cada um `standardize(tanh(2*u*v)+0.35*(u+v)/sqrt(2))`. Seu subtipo é `interaction_marginal_signal`, distinto da interação pura histórica.

A verdade conhecida conserva sinais e redundâncias: 12/20/30/60 features relevantes. Pesos, índices dos termos, permutação de colunas e grupos de intensidade ficam nos metadados. Grupos podem se sobrepor: Industrial x0 participa de termo forte e interação fraca. As redundâncias herdam a intensidade de sua origem. Bioinformática classifica 0,35 como médio. O recall global continua principal; recall por intensidade e subtipo são complementares.

A calibração sintética é conjunta treino/teste, determinística por seed, com termos e ruído padronizados, seguida de split estratificado. Nenhum modelo é ajustado no teste. Cache inclui versão/hash do gerador e perfil. As mudanças são iguais para todos os métodos. Redução da saturação e recuperação de efeitos marginais são hipóteses para uma campanha futura.

### Uso local

```sh
uv sync --locked
uv run pytest -q
uv run python scripts/verify_smoke.py
# Qualquer perfil pode ser selecionado; use diretórios próprios para smokes parciais.
uv run python scripts/verify_smoke.py --dataset bioinformatica --results /tmp/bio-v2/results --output /tmp/bio-v2/report
```

O smoke usa diretórios exclusivos sob `verification/v2-a6-r5-local`. O comando verifica sucesso, relatórios provisórios e retomada byte a byte. A identidade do protocolo, dependências, fonte e configuração fazem parte dos manifests; manifest incompatível exige outro ID. Agregação recusa mistura de protocolos/fontes/dependências.

### Medição e métricas

Cada fit roda em processo novo. Carregamento, preparação e avaliação downstream ficam fora do cronômetro e da coleta de memória do seletor. RSS é amostrado a cada 5 ms; Linux também registra VmHWM e tentativa de reset antes do fit. Quando o reset falha, o high-water mark é explicitamente de toda a vida do processo. Delta de pico subtrai o baseline. Buffers explícitos e bytes copiados são diagnósticos separados de RSS; valores numéricos recebem mediana/IQR nos resumos.

Linux lê package/core IDs no sysfs e cruza com a afinidade permitida. Seleciona um processador lógico por núcleo, em conjuntos aninhados de 1/2/4/8/16. Recusa topologia ausente ou núcleos insuficientes e confere afinidade efetiva. Registra fabricante, modelo, topologia permitida, CPUs selecionadas e afinidade. macOS smoke declara essas verificações indisponíveis. OpenMP, Rayon e `n_jobs` seguem o número solicitado; BLAS, NumExpr e Accelerate usam uma thread. A campanha de escala mede somente 4, 8 e 16 núcleos, com baseline próprio de 4 núcleos.

Precisão, recall, F1, FDR, falsos positivos trap e seleções tentativas são reportados. Downstream usa ExtraTrees com 200 árvores, max_features sqrt, class_weight balanced, somente features confirmadas; registra AUC, accuracy, balanced accuracy e F1. Oracle e todas as features são referências em processos próprios. Medianas e quartis usam quantile linear; falhas nunca viram observações zero. Smoke ou campanhas incompletas não geram placeholders finais.

### Campanha AMD do protocolo v2

Alvo: `c7a.4xlarge`, AMD EPYC, 16 núcleos físicos, uma thread por núcleo, 32 GiB ([especificação AWS](https://docs.aws.amazon.com/ec2/latest/instancetypes/co.html)). ECS sobre EC2, uma tarefa por host, reserva 16 CPUs e 28 GiB. `MACHINE` em `config.py` centraliza a identidade; templates e placement usam esse alvo, capacidade desejada zero nos planos offline.

Qualidade: quatro perfis × quatro métodos × cinco seeds (42–46) × 16 núcleos = 80 fits. Escala: Industrial × quatro métodos × cinco seeds × 4/8/16 núcleos = 60 fits independentes. Dois warmups por célula usam seeds 900001/900002. Não reutilizar observações anteriores ou da a4.

O teto aprovado é R$400, com R$80 protegidos. O ledger atual foi reconciliado e permite R$100 em novas reservas. A próxima etapa é uma calibração Industrial full limitada a três horas (R$60 reservados atomicamente); ela medirá duração e memória, sem concluir a campanha de qualidade. As campanhas de 80/60 fits continuam condicionadas à análise dessa calibração.

```sh
# Executar somente depois da aceitação Linux/container e aprovação da campanha futura.
uv run bankai-benchmark full --suite quality --experiment paper-v2-a6-amd16-r5 --results results-v2
uv run bankai-benchmark full --suite scaling --experiment paper-v2-a6-amd16-r5 --results results-v2
uv run bankai-aggregate --results results-v2 --output reports-v2
uv run python scripts/analyze_campaign.py --quality results-v2/paper-v2-a6-amd16-r5-quality --scaling results-v2/paper-v2-a6-amd16-r5-scaling --output reports-v2/analysis
```

A campanha v2 de escala usa baseline de quatro CPUs e apenas observações novas. A campanha full não foi iniciada: o smoke comprova funcionamento, e a liberação dos lotes depende da reconciliação do ledger e da calibração autorizada descrita em BUDGET.md. Consulte [validação](VERIFICATION.md), [infraestrutura](deployment/README.md), [orçamento](BUDGET.md) e [dependências/licenças](DEPENDENCIES.md).

### Histórico preservado

[README a4 de 17/10/2026](docs/history/a4-20261017/README.md) contém resultados e instruções daquela campanha, não defaults v2. Resultados sob `verification/campaign-20261017`, `verification/pilot-20261017`, `results-public-a4*` e relatórios existentes não foram recalculados. Checksums históricos continuam válidos. `config-paper-v1.json` preserva o mapeamento antigo; leitores usam o manifest para escolher o protocolo. `scaling48.py` aceita somente arquivos históricos e recusa execução v2; o controlador antigo não é o caminho da nova escala.

### Candidato exato a7

A otimização a7/RF a16 tem [protocolo, diagnósticos, reprodução e critérios próprios](docs/exact-session-a7.md). Ela foi publicada e depois substituída pelas versões medidas em [Resultados atuais](#resultados-atuais-010a12).
