# Bankai Boruta benchmark

Benchmark reproduzível do [Bankai Boruta](https://github.com/breno-jesus-fernandes/bankai-boruta) contra o BorutaPy. A rodada mais recente usa o protocolo `native-shadow-max40-v1` com o **Bankai Boruta 0.1.0a12** e o **BankaiRF 0.1.0a20**, publicados no PyPI, com dados 2× numa máquina de 32 núcleos. As rodadas anteriores continuam documentadas abaixo, da mais nova para a mais antiga.

## Histórico dos benchmarks

| Data | Rodada | Versões | Máquina | Dados | Resultado principal | Detalhes |
|---|---|---|---|---|---|---|
| 31/10/2026 | Native-shadow 2× | 0.1.0a12 / RF 0.1.0a20 | c7a.8xlarge, 32 núcleos | 4 perfis com N e P dobrados, 5 seeds × 5 repetições; CIC-IDS2017 | Bankai exato de 1,9 a 8,0× mais rápido que o BorutaPy + ExtraTrees, com metade da memória; precisão 1,00 nos 400 fits | [2×](#dados-2-em-32-núcleos-31102026) |
| 23/10/2026 | Native-shadow a12 | 0.1.0a12 / RF 0.1.0a20 | c7a.4xlarge, 16 núcleos | 4 perfis, 5 seeds × 5 repetições; CIC-IDS2017 | Bankai exato com 76% menos tempo (mediana) e 48% menos memória que o BorutaPy + ExtraTrees | [a12](#0110a12-em-16-núcleos-23102026) |
| 23/10/2026 | CIC-IDS2017 a8 | 0.1.0a8 / RF 0.1.0a17 | c7a.4xlarge, 16 núcleos | CIC-IDS2017, 5 seeds | Bankai exato 98,7 s contra 128,8 s do BorutaPy + ExtraTrees, mas com mais memória (5,0 contra 4,0 GiB); motivou a a12 | [a12 vs a8](verification/native-shadow-cicids2017-a12-amd-20261023/README.md) |
| 19/10/2026 | Native-shadow a8 | 0.1.0a8 / RF 0.1.0a17 | c7a.4xlarge, 16 núcleos | 4 perfis, 5 seeds; escala 4/8/16 threads na Industrial | Bankai exato mais rápido que o BorutaPy + ExtraTrees em 20/20 pares (0,27–0,96 do tempo); de 4 para 16 threads, o Bankai ficou ~3× mais rápido e o BorutaPy 1,8–1,9× | [perfis](verification/native-shadow-amd-20261019/README.md), [escala](verification/native-shadow-scaling-amd-20261019/README.md) |
| 18/10/2026 | Candidato exato a7 | 0.1.0a7 / RF 0.1.0a16 | c7a.4xlarge, 16 núcleos | Industrial, piloto de 40 rodadas | Sessão exata sem matriz de shadows; base do protocolo native-shadow | [a7](docs/exact-session-a7.md) |
| 18/10/2026 | Protocolo v2 | 0.1.0a6 / RF 0.1.0a15 | c7a.4xlarge, 16 núcleos | Smoke ECS e calibração interrompida | Sem resultados de desempenho | [v2](#protocolo-v2-a6-histórico) |
| 17/10/2026 | Campanha a4 | 0.1.0a4 | c7i.4xlarge, 16 vCPUs Intel | 4 perfis, 5 seeds, 210 medições | Bankai 1,50× mais rápido que o BorutaPy + ExtraTrees e 1,57× que o BorutaPy + LightGBM (média geométrica) | [a4](docs/history/a4-20261017/README.md) |

## Protocolo native-shadow

- **Métodos:**
  - Bankai exato: Extra Trees do BankaiRF com cortes nos valores originais;
  - Bankai bins: Extra Trees do BankaiRF com 63 bins;
  - BorutaPy + ExtraTrees: BorutaPy 0.4.3 com o `ExtraTreesClassifier` do scikit-learn 1.9.1;
  - BorutaPy + LightGBM: BorutaPy com LightGBM em modo random forest (63 bins, subamostragem 0,8).
- **Configuração comum:** árvores, profundidade e fração de features de cada perfil, bootstrap, `perc=100`, `alpha=0.05`, `two_step=True`, no máximo 40 rodadas com parada natural, float32 e seeds 42–46.
- **Medição:**
  - cada fit roda num processo novo, depois de gerar os dados;
  - o tempo cobre só o `fit`;
  - a memória é o pico de RSS acima do que os dados já ocupam, amostrado de fora a cada 5 ms;
  - a AUC vem de um ExtraTrees de 200 árvores treinado só com as features confirmadas e avaliado no teste.

## Dados 2× em 32 núcleos (31/10/2026)

Os quatro perfis sintéticos com N e P dobrados (`--scale 2`) e as mesmas features relevantes, de modo que só o ruído cresce, numa EC2 c7a.8xlarge (32 núcleos AMD físicos, SMT desligado, 64 GiB) com 32 threads. Métodos, versões (0.1.0a12/0.1.0a20) e protocolo são os mesmos da [rodada de 16 núcleos](#0110a12-em-16-núcleos-23102026); cinco seeds × cinco repetições, 400 fits ([detalhes](verification/native-shadow-x2-a12-amd32-20261031/README.md)). As colunas 1× repetem a tabela dessa rodada.

| Perfil (treino n × p, relevantes) | Método | Tempo (s) | RSS (MiB) | Precisão | Recall | AUC | Tempo 1× (s) | Recall 1× |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Industrial 400k × 1.000 (12) | Bankai exato | **15,5** | 3.490 | 1,00 | 0,67 | 0,840 | 9,2 | 0,67 |
| | Bankai bins | 19,8 | **1.592** | 1,00 | 0,67 | 0,840 | 10,8 | 0,67 |
| | BorutaPy + ExtraTrees | 123,9 | 6.945 | 1,00 | 0,67 | 0,840 | 37,1 | 0,67 |
| | BorutaPy + LightGBM | 186,7 | 13.208 | 1,00 | 0,67 | 0,840 | 75,1 | 0,67 |
| Crédito 600k × 600 (20) | Bankai exato | **17,3** | 3.406 | 1,00 | 0,85 | 0,854 | 9,5 | 0,85 |
| | Bankai bins | 23,3 | **1.698** | 1,00 | 0,85 | 0,854 | 10,9 | 0,85 |
| | BorutaPy + ExtraTrees | 125,0 | 6.758 | 1,00 | 0,85 | 0,854 | 46,2 | 0,85 |
| | BorutaPy + LightGBM | 154,5 | 9.951 | 1,00 | 0,85 | 0,854 | 52,7 | 0,85 |
| Cibersegurança 800k × 300 (60) | Bankai exato | **37,4** | 2.744 | 1,00 | 0,70 | 0,838 | 24,5 | 0,67 |
| | Bankai bins | 38,6 | **1.590** | 1,00 | 0,77 | 0,838 | 23,5 | 0,62 |
| | BorutaPy + ExtraTrees | 202,3 | 5.413 | 1,00 | 0,70 | 0,839 | 110,4 | 0,65 |
| | BorutaPy + LightGBM | 164,3 | 5.934 | 1,00 | 0,67 | 0,839 | 79,9 | 0,55 |
| Bioinformática 100k × 4.000 (30) | Bankai exato | 173,5 | 3.193 | 1,00 | 1,00 | 0,755 | 85,7 | 1,00 |
| | Bankai bins | **162,2** | **1.303** | 1,00 | 1,00 | 0,755 | 71,1 | 1,00 |
| | BorutaPy + ExtraTrees | 337,2 | 6.378 | 1,00 | 1,00 | 0,755 | 145,1 | 1,00 |
| | BorutaPy + LightGBM | 338,7 | 22.290 | 1,00 | 1,00 | 0,755 | 130,0 | 0,80 |

- **Tempo e memória:** os dois modos do Bankai foram mais rápidos e usaram menos memória que BorutaPy + ExtraTrees e BorutaPy + LightGBM em todas as 20 combinações de perfil e seed.
  - Com quatro vezes mais dados e o dobro de núcleos, o Bankai exato levou de 1,5 a 2,0 vezes o tempo do 1×; o BorutaPy + ExtraTrees, de 1,8 a 3,3 vezes.
  - A vantagem do Bankai exato sobre o BorutaPy + ExtraTrees cresceu em todos os perfis: 8,0× na Industrial (4,0× no 1×), 7,2× no Crédito (4,9×), 5,4× na Cibersegurança (4,5×) e 1,9× na Bioinformática (1,7×).
  - O Bankai exato usa cerca de metade da memória do BorutaPy + ExtraTrees, e o modo com bins de 20% a 30%. Na Bioinformática, o BorutaPy + LightGBM chegou a 21,8 GiB, 17 vezes o Bankai bins.
- **Seleção:**
  - Nenhum método confirmou feature irrelevante nos 400 fits, e cada método confirmou o mesmo conjunto nas cinco repetições de cada seed.
  - Em Industrial, Crédito e Bioinformática, os quatro métodos confirmaram os mesmos conjuntos em todas as seeds. Com o dobro de linhas, o BorutaPy + LightGBM passou a achar as 30 relevantes da Bioinformática.
  - Na Cibersegurança, todos chegaram às 40 rodadas e o recall subiu em todos os métodos. O Bankai exato coincidiu com o BorutaPy + ExtraTrees em três seeds e diferiu em uma ou duas features limítrofes nas outras duas.
- **AUC:** onde os conjuntos coincidem, a AUC é a mesma. Na Cibersegurança, os quatro métodos ficaram entre 0,838 e 0,839. Em todos os perfis, a seleção supera o modelo com todas as features (0,815; 0,810; 0,801; 0,684).

### CIC-IDS2017 em 32 núcleos

Os mesmos dados reais, sem escala, com 32 threads na c7a.8xlarge ([detalhes](verification/native-shadow-cicids2017-a12-amd32-20261031/README.md)).

| Método | Tempo (s) | RSS (MiB) | s/rodada | Rodadas | Confirmadas | AUC | Tempo com 16 threads (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Bankai exato | **22,3** | 3.033 | 1,84 | 12 | 68 | 0,99872 | 39,8 |
| Bankai bins | 75,3 | **2.428** | 1,88 | 40 | 66 | 0,99874 | 129,2 |
| BorutaPy + ExtraTrees | 92,1 | 5.888 | 7,72 | 12 | 68 | 0,99872 | 130,8 |
| BorutaPy + LightGBM | 250,6 | 2.759 | 6,27 | 40 | 66 | 0,99874 | 280,3 |

Cada método confirmou as mesmas features, no mesmo número de rodadas, que com 16 threads, em todas as seeds. Com o dobro de núcleos, o Bankai exato ficou 1,8 vez mais rápido, contra 1,4 do BorutaPy + ExtraTrees e 1,1 do BorutaPy + LightGBM, e agora é 4,1 vezes mais rápido que o BorutaPy + ExtraTrees. Os buffers por thread somam cerca de 0,9 GiB aos dois modos do Bankai e 1,7 GiB ao BorutaPy + ExtraTrees.

### Reproduzir 2×

Custos e etapas em [política de preço 2×](verification/native-shadow-x2-cost-policy-20261030.md).

```sh
BANKAI_BENCHMARK_SRC=src uv run --no-sync python scripts/native_shadow_pilot.py --datasets industrial --seeds 42 --repeats 1 --threads 8 --scale 2 --output-dir /tmp/ns2
# Na AWS, com a imagem native-shadow publicada (a12/a20), um lançamento por perfil, como na campanha:
uv run python scripts/run_native_shadow_aws.py --image <uri@sha256> --subnets <subnet> --security-groups <sg> \
  --instance c7a.8xlarge --scale 2 --datasets industrial --seeds 42 43 44 45 46 --repeats 5 --hours 4 \
  --stack bankai-ns-x2-industrial --state verification/native-shadow-x2-industrial.json
# O runner zera a frota no fim; a stack é apagada depois que o host termina.
aws cloudformation delete-stack --stack-name bankai-ns-x2-industrial
```

Se a sessão AWS local expirar durante o acompanhamento, o runner espera um novo `aws login` (o desligamento armado limita o custo) e `--resume <state.json>` finaliza o lançamento a partir do estado. Com `--threads 8 16 32 64`, uma tarefa roda o piloto uma vez por contagem de threads no mesmo host; `--auc` grava a AUC no próprio artefato.

A AUC dos perfis 2× grandes não cabe na memória de um notebook; `scripts/run_native_shadow_auc_aws.py --image <uri@sha256> --artifacts <dir> --subnets <subnet> --security-groups <sg> --state <json>` a calcula numa c7a.8xlarge e grava o `auc.json` de volta na pasta.

Na AWS, `scripts/run_candidate_probe_aws.py` sobe a stack, roda wheels Linux escolhidas (`--wheel`, `--extra-wheel`) sobre a imagem publicada e apaga a stack no fim. O desligamento é armado antes de qualquer capacidade, e as horas são reservadas no ledger de [orçamento](BUDGET.md).

## 0.1.0a12 em 16 núcleos (23/10/2026)

- **Máquina:** uma EC2 c7a.4xlarge (16 núcleos AMD físicos, SMT desligado, 32 GiB) no ECS, 16 threads.

### Perfis sintéticos

Mediana sobre cinco seeds, cada uma a mediana de cinco repetições ([detalhes](verification/native-shadow-synthetic-a12-r5-amd-20261023/README.md)).

| Perfil (treino n × p, relevantes) | Método | Tempo (s) | RSS (MiB) | Precisão | Recall | AUC |
|---|---|---:|---:|---:|---:|---:|
| Industrial 200k × 500 (12) | Bankai exato | **9,2** | 931 | 1,00 | 0,67 | 0,837 |
| | Bankai bins | 10,8 | **456** | 1,00 | 0,67 | 0,837 |
| | BorutaPy + ExtraTrees | 37,1 | 1.816 | 1,00 | 0,67 | 0,837 |
| | BorutaPy + LightGBM | 75,1 | 4.865 | 1,00 | 0,67 | 0,837 |
| Crédito 300k × 300 (20) | Bankai exato | **9,5** | 929 | 1,00 | 0,85 | 0,852 |
| | Bankai bins | 10,9 | **506** | 1,00 | 0,85 | 0,852 |
| | BorutaPy + ExtraTrees | 46,2 | 1.805 | 1,00 | 0,85 | 0,852 |
| | BorutaPy + LightGBM | 52,7 | 3.429 | 1,00 | 0,85 | 0,852 |
| Cibersegurança 400k × 150 (60) | Bankai exato | 24,5 | 760 | 1,00 | 0,67 | 0,837 |
| | Bankai bins | **23,5** | **476** | 1,00 | 0,62 | 0,838 |
| | BorutaPy + ExtraTrees | 110,4 | 1.455 | 1,00 | 0,65 | 0,836 |
| | BorutaPy + LightGBM | 79,9 | 1.877 | 1,00 | 0,55 | 0,837 |
| Bioinformática 50k × 2000 (30) | Bankai exato | 85,7 | 853 | 1,00 | 1,00 | 0,750 |
| | Bankai bins | **71,1** | **388** | 1,00 | 1,00 | 0,750 |
| | BorutaPy + ExtraTrees | 145,1 | 1.608 | 1,00 | 1,00 | 0,750 |
| | BorutaPy + LightGBM | 130,0 | 5.823 | 1,00 | 0,80 | 0,734 |

- **Tempo e memória:** os dois modos do Bankai foram mais rápidos e usaram menos memória que BorutaPy + ExtraTrees e BorutaPy + LightGBM em todas as 20 combinações de perfil e seed.
  - Frente ao BorutaPy + ExtraTrees, o Bankai exato gastou em mediana 76% menos tempo (de 41% a 87%) e 48% menos memória.
  - Frente ao BorutaPy + ExtraTrees, o modo com bins gastou 76% menos tempo e 73% menos memória.
- **Seleção:**
  - Nenhum método confirmou feature irrelevante.
  - Em Industrial, Crédito e Bioinformática, Bankai exato, Bankai bins e BorutaPy + ExtraTrees confirmaram os mesmos conjuntos em todas as seeds.
  - Na Cibersegurança, todos chegaram às 40 rodadas, e os conjuntos diferem em uma a quatro features limítrofes por seed.
  - O BorutaPy + LightGBM perdeu até 12 das 30 relevantes na Bioinformática.
- **Contra o 0.1.0a8:** o Bankai exato ficou de 1,6 a 2,5 vezes mais rápido e usa de 13% a 46% menos memória, com seleções idênticas em todos os perfis, seeds e repetições.

### CIC-IDS2017 (dados reais)

Base de treino com 1.748.586 linhas e 78 colunas em float32 (`scripts/prepare_cicids2017.py`), com a configuração do perfil Cibersegurança e uma repetição por seed ([detalhes](verification/native-shadow-cicids2017-a12-amd-20261023/README.md)).

| Método | Tempo (s) | RSS (MiB) | s/rodada | Rodadas | Confirmadas | AUC |
|---|---:|---:|---:|---:|---:|---:|
| Bankai exato | **39,8** | 2.140 | 3,29 | 12 | 68 | 0,99872 |
| Bankai bins | 129,2 | **1.517** | 3,23 | 40 | 66 | 0,99874 |
| BorutaPy + ExtraTrees | 130,8 | 4.146 | 11,0 | 12 | 68 | 0,99872 |
| BorutaPy + LightGBM | 280,3 | 2.736 | 7,02 | 40 | 66 | 0,99874 |

O Bankai exato confirmou as mesmas 68 features que o BorutaPy + ExtraTrees em todas as seeds, 3,3 vezes mais rápido e com cerca de metade da memória. Com todas as 78 features, a AUC é 0,99871.

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

A otimização a7/RF a16 tem [protocolo, diagnósticos, reprodução e critérios próprios](docs/exact-session-a7.md). Ela foi publicada e depois substituída pelas versões medidas em [0.1.0a12 em 16 núcleos](#0110a12-em-16-núcleos-23102026).
