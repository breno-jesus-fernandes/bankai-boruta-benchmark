# Candidato exato a7: protocolo independente

O protocolo publicado `paper-v2-a6-amd16-r5`, seus pins a6/a15, gerador, imagens,
locks e artefatos históricos permanecem congelados. A otimização tem identidade
própria `exact-session-a7-v1`; seus JSONs não entram no agregador de resultados r5.
A a7 e o RF a16 ainda são candidatos de release. Não instalar uma versão inexistente
do PyPI nem substituir o lock r5 para executar o candidato.

## Implementação e interpretação

O RF a16 fornece um banco imutável compartilhado e mapas explícitos de shadows.
A a7 cria uma sessão por fit, valida o banco uma vez, conserva a ordenação real
quando a lista ativa não muda e refina apenas empates usando shadows e labels.
A leitura do treinamento reproduz f32 da referência nativa. Shuffle, draws do
RandomState, seeds, bootstrap, orçamento de árvores e critérios de parada são
preservados. Caminhos públicos float64 continuam usando o adaptador a6 com
precisão float64; não devem ser convertidos para f32 para obter um ganho artificial.

O caminho novo é optativo (`BANKAI_BORUTA_EXACT_SESSION=1`), condicionado à
paridade e a reduções medidas de RSS e tempo mediano no AMD. O padrão continua
materializado. `copied_bytes=0` na a6 cobre somente cópias Python e não significa
que o RF não construa uma matriz real+shadows. Na sessão, um snapshot do banco
real e permutações explícitas continuam vivos. No caso padrão MT19937/u32, o
shuffle idêntico ocorre diretamente no buffer da sessão, trocando o estado do RNG
antes do draw de seed. Subclasses de RNG e índices int64 usam o fallback NumPy
com snapshot Rust reutilizado e copiado por round. Contabilizar ambos e não confundir bytes vivos com o
volume acumulado de cópias. Tempos de validação, shuffle, ordenação, armazenamento
e treinamento e capacidades conhecidas são reportados separadamente. Workspaces
medidos não incluem toda a floresta: RSS externo e VmHWM são necessários.

Com `verbose>=2`, a a7 registra largura ativa, seed, duração, hits, decisões e
motivo final de parada por round. Desativar esse trace nos experimentos de tempo.
A documentação completa e os limites dos diagnósticos estão em
[Bankai Boruta, docs/exact-session.md](https://github.com/breno-jesus-fernandes/bankai-boruta/blob/perf/exact-session-a7/docs/exact-session.md).

## Reprodução local e Linux

Use dois ambientes: referência congelada a6/a15 e candidato a7/a16. A fonte Rust
e o override de desenvolvimento Python da a7 apontam para a revisão imutável
RF `da52a5bc0e2358911131d3b06d9cea65fc360505`. O pin de distribuição será
`bankai-random-forest==0.1.0a16`, a publicar antes da a7. O benchmark não altera
seu próprio ambiente r5.

O script versionado `benchmarks/compare_exact_session.py` do checkout Boruta
executa dois processos novos sequencialmente, alterna a ordem por repetição,
verifica versões da referência, hash dos dados, hits, decisões, seleções,
tentativas, ranking, rounds e parada; compara importâncias e thresholds com
atol=rtol=1e-12. Registra hashes do seletor e binário, versões, configuração,
observações individuais, medianas e quartis. Recusa sobrescrita da saída.

```sh
# No checkout Boruta candidato; referência separada.
uv venv .venv-reference --python 3.13
uv pip install --python .venv-reference/bin/python bankai-boruta==0.1.0a6 bankai-random-forest==0.1.0a15
uv sync --locked --extra test
uv run --no-sync maturin develop --release --locked
uv run --no-sync pytest -q
uv run --no-sync python benchmarks/compare_exact_session.py --reference-python "$PWD/.venv-reference/bin/python" --candidate-python "$PWD/.venv/bin/python" --output /tmp/exact-a7-fixed-t1.json
uv run --no-sync python benchmarks/compare_exact_session.py --reference-python "$PWD/.venv-reference/bin/python" --candidate-python "$PWD/.venv/bin/python" --rows 2000 --columns 40 --trees 10 --fixed-rounds 0 --output /tmp/exact-a7-complete-t1.json
```

A coleta RSS externa amostra somente o fit, a cada 5 ms, usando um handshake
ready/go/done. No Linux, o worker tenta resetar VmHWM e registra se o escopo é
fit ou vida inteira do processo. Geração/hash/serialização dos dados ficam fora
da coleta e do tempo do seletor. Não executar builds ou outros testes durante
as medições. Rodadas fixas medem eficiência; fits completos também medem
convergência. Não normalizar ou ajustar a parada para favorecer um método.

## Aceitação AMD ainda pendente

Executar no mesmo host dedicado, sequencialmente, workers **1/4/16**, seeds
**42–46**, três repetições por célula, tanto rodadas fixas quanto Industrial full.
Para o gerador Industrial congelado deste repositório, acrescentar ao script
`--benchmark-root /caminho/bankai-boruta-benchmark --trees 100`; para fit completo,
usar `--fixed-rounds 0 --max-iter 120`. Demais parâmetros são os mesmos do exato
r5 (depth 6, sqrt, bootstrap, paciência 100). Usar caminhos distintos por
seed/workers/repetição; nunca apontar para diretórios a6. Nenhum resultado macOS
ou runner hospedado comprova ganho no AMD dedicado.

A campanha completa de 1/4/16 workers é diferente da calibração r5 registrada em
[BUDGET.md](../BUDGET.md). Não reinterpretar a reserva existente como autorização
ilimitada nem consumir a reserva protegida. Antes do lançamento, reconciliar o
ledger existente, estimar a duração a partir de pilotos, reservar somente saldo
autorizado e verificar deadline e desligamento automático. Se o lote exceder o
saldo/tempo autorizado, registrar a parte pendente e pedir autorização adicional.
Nesta entrega não houve alocação de AWS nem alteração do ledger.

O workflow Boruta prepara evidência Linux de paridade e workloads controlados.
A ativação por padrão permanece bloqueada até passar em ambos os critérios de
memória e tempo e na paridade, inclusive Industrial completo. Se a leitura
indireta regredir, ajustar os buffers e repetir os experimentos antes de ativar.

## Release

Revisar e publicar RF a16 primeiro, depois testar a instalação pública limpa e
publicar Boruta a7. Os dois workflows exigem dispatch explícito `publish=true`
para PyPI; criar PR não publica os pacotes. Não trocar a imagem/lock r5 pelo
candidato antes de criar e validar um novo manifest, digest e orçamento próprios.
Os [relatórios e observações locais](../verification/exact-session-a7-local/README.md)
ficam em `verification/exact-session-a7-local/`, com SHA256 por artefato no manifest.
Na matriz controlada 50.000 × 200, o candidato reduziu a mediana de tempo em 25,9%
e o pico RSS mediano em 11,2% (um worker); com quatro workers, 27,7% e 7,0%.
O caso pequeno de rodadas fixas com um worker não reduziu RSS absoluto. Todos
passaram em paridade. Esses números macOS não substituem Industrial/AMD.

PRs: [BankaiRF #21](https://github.com/breno-jesus-fernandes/bankai-random-forest/pull/21)
e [Bankai Boruta #20](https://github.com/breno-jesus-fernandes/bankai-boruta/pull/20).
Ambas permanecem draft até a revisão dos gates pendentes.
