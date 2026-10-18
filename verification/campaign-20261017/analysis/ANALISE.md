# Resultados consolidados

210 medições únicas: 140 de qualidade e 70 novas de escala. Na escala, 35 observações de qualidade a 16 threads são reutilizadas, sem contá-las novamente como execuções.

## Principais observações

- Bankai Classic nativo apresentou o menor tempo mediano entre as sete configurações em cada um dos quatro perfis de qualidade.
- Comparado ao adapter, o Classic nativo preservou as seleções confirmadas nos 20/20 pares. A redução mediana por seed foi de 14.6–17.8% em tempo e 30.9–40.0% em pico RSS, dependendo do dataset.
- BorutaPy–ExtraTrees apresentou o menor pico RSS mediano nos quatro datasets. A vantagem de memória do caminho nativo é em relação ao adapter, não uma liderança universal de memória.
- Em Bioinformática, Classic nativo/adapter e BorutaPy–LightGBM encontraram 10/30 features relevantes (recall 0,333) em todos os seeds: os dez sinais correlacionados e nenhuma das vinte features de interação. Os Greedy aumentaram modestamente o recall, junto com falsos positivos.
- Na escala Industrial, os quatro métodos com BankaiRF tiveram menor tempo mediano em 8 threads que em 16. Os dois métodos LightGBM tiveram menor tempo mediano em 16. A diferença de ExtraTrees foi pequena. Isso não estabelece um número de threads ótimo para outros perfis.
- O oracle downstream é uma referência com features verdadeiras; seu desempenho depende do próprio ExtraTrees avaliador e não é o limite ótimo teórico do problema.

## Qualidade — 16 threads

Medianas de cinco seeds. Quartis/IQR e referências oracle/todas as features estão no CSV.

| Dataset | Método | Fit (s) | Pico GiB | Precisão | Recall | AUC |
|---|---|---:|---:|---:|---:|---:|
| industrial | bankai_classic_native | 23.60 | 1.36 | 1.000 | 1.000 | 0.8758 |
| industrial | bankai_classic_adapter | 28.86 | 2.24 | 1.000 | 1.000 | 0.8758 |
| industrial | bankai_greedy_native | 36.71 | 1.36 | 0.462 | 1.000 | 0.8734 |
| industrial | borutapy_lightgbm_rf | 51.25 | 2.77 | 1.000 | 1.000 | 0.8740 |
| industrial | borutapy_sklearn_et | 37.72 | 1.18 | 1.000 | 1.000 | 0.8758 |
| industrial | greedy_borutapy_bankai | 39.99 | 1.52 | 0.462 | 1.000 | 0.8734 |
| industrial | greedy_borutapy_lightgbm | 64.52 | 2.93 | 0.600 | 1.000 | 0.8742 |
| credito | bankai_classic_native | 23.73 | 1.33 | 1.000 | 1.000 | 0.8597 |
| credito | bankai_classic_adapter | 28.68 | 2.10 | 1.000 | 1.000 | 0.8597 |
| credito | bankai_greedy_native | 30.20 | 1.32 | 0.690 | 1.000 | 0.8588 |
| credito | borutapy_lightgbm_rf | 38.26 | 2.85 | 1.000 | 1.000 | 0.8597 |
| credito | borutapy_sklearn_et | 26.72 | 1.13 | 1.000 | 1.000 | 0.8597 |
| credito | greedy_borutapy_bankai | 33.38 | 1.43 | 0.690 | 1.000 | 0.8588 |
| credito | greedy_borutapy_lightgbm | 51.91 | 2.69 | 0.588 | 1.000 | 0.8592 |
| bioinformatica | bankai_classic_native | 53.66 | 1.29 | 1.000 | 0.333 | 0.6969 |
| bioinformatica | bankai_classic_adapter | 63.35 | 2.15 | 1.000 | 0.333 | 0.6969 |
| bioinformatica | bankai_greedy_native | 97.40 | 1.29 | 0.429 | 0.367 | 0.7029 |
| bioinformatica | borutapy_lightgbm_rf | 69.20 | 3.80 | 1.000 | 0.333 | 0.6969 |
| bioinformatica | borutapy_sklearn_et | 117.86 | 1.13 | 0.667 | 0.333 | 0.6997 |
| bioinformatica | greedy_borutapy_bankai | 98.85 | 1.44 | 0.429 | 0.367 | 0.7029 |
| bioinformatica | greedy_borutapy_lightgbm | 113.13 | 3.97 | 0.224 | 0.367 | 0.7044 |
| ciberseguranca | bankai_classic_native | 20.53 | 1.16 | 1.000 | 1.000 | 0.8744 |
| ciberseguranca | bankai_classic_adapter | 23.88 | 1.67 | 1.000 | 1.000 | 0.8744 |
| ciberseguranca | bankai_greedy_native | 23.67 | 1.15 | 0.870 | 1.000 | 0.8721 |
| ciberseguranca | borutapy_lightgbm_rf | 34.43 | 1.60 | 1.000 | 1.000 | 0.8744 |
| ciberseguranca | borutapy_sklearn_et | 27.40 | 0.90 | 1.000 | 1.000 | 0.8744 |
| ciberseguranca | greedy_borutapy_bankai | 24.76 | 1.18 | 0.870 | 1.000 | 0.8721 |
| ciberseguranca | greedy_borutapy_lightgbm | 33.30 | 1.71 | 0.896 | 1.000 | 0.8714 |

## Classic nativo versus adapter

Reduções calculadas em cada seed e depois resumidas pela mediana.

| Dataset | Redução do tempo | Redução de pico RSS | Seleções confirmadas idênticas |
|---|---:|---:|---:|
| industrial | 16.3% | 39.2% | 5/5 |
| credito | 17.8% | 37.1% | 5/5 |
| bioinformatica | 15.5% | 40.0% | 5/5 |
| ciberseguranca | 14.6% | 30.9% | 5/5 |

## Escala — Industrial

Speedup pareado relativo a 4 threads; os dados de 16 threads vêm da qualidade. Nenhuma medição a 1 ou 2 threads foi realizada.

| Método | Fit 4 (s) | Fit 8 (s) | Fit 16 (s) | Speedup 8/4 | Speedup 16/4 |
|---|---:|---:|---:|---:|---:|
| bankai_classic_native | 36.84 | 22.32 | 23.60 | 1.651 | 1.524 |
| bankai_classic_adapter | 36.25 | 26.83 | 28.86 | 1.351 | 1.242 |
| bankai_greedy_native | 56.29 | 33.28 | 36.71 | 1.703 | 1.533 |
| borutapy_lightgbm_rf | 70.02 | 52.08 | 51.25 | 1.345 | 1.358 |
| borutapy_sklearn_et | 57.44 | 37.50 | 37.72 | 1.531 | 1.521 |
| greedy_borutapy_bankai | 50.29 | 36.45 | 39.99 | 1.378 | 1.253 |
| greedy_borutapy_lightgbm | 94.81 | 69.06 | 64.52 | 1.374 | 1.465 |

## Limites de interpretação

- Cinco seeds medem variação entre realizações sintéticas; não são cinco repetições do mesmo dataset nem cinco máquinas independentes.
- As medições foram sequenciais. A comparação 8/16 reutiliza uma campanha anterior e não separa completamente efeitos de ordem, host e caches do efeito das threads.
- Mediana e Q1–Q3 descrevem os dados; o IQR não é intervalo de confiança. Não afirmamos significância estatística.
- Os quatro datasets são sintéticos e têm um SNR/perfil fixo cada; os resultados não demonstram generalização para dados reais ou outros perfis.
- Backends diferem em bootstrap, amostragem e splits; a comparação nativo/adapter do mesmo BankaiRF isola melhor o caminho de execução.
- Bioinformática revelou baixo recall das interações: isso é uma limitação observada do perfil testado, não evidência de recuperar todas as features relevantes.
- Eficiência da escala é relativa a quatro threads; sem uma thread não há eficiência paralela convencional.

## Artefatos

- `quality/`: CSVs, tabelas TeX e placeholders Industrial/16 threads.
- `scaling/`: mediana/IQR, speedups por seed e origem das 35 observações reutilizadas.
- `paired_quality_comparisons.csv`: comparações por seed, paridade da seleção e diferenças de AUC/recall.
- `paired_8_vs_16.csv`: diferenças pareadas entre a campanha nova de 8 threads e os 16 threads reutilizados.
- `figures/`: gráficos SVG/PDF/PNG reproduzíveis, sem gráficos gerados por IA.
- `validation.json`: contagens e paridade confirmadas; não substitui revisão metodológica do artigo.
