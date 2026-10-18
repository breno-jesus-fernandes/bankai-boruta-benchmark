# Validação local — 18/10/2026

Protocolo `paper-v2-a5-amd16`, gerador 2.0.0. Execução em macOS; nenhum recurso AWS iniciado, nenhum workflow remoto disparado, nenhuma imagem ou resultado de desempenho publicado.

- `uv sync --locked`: passou; Bankai Boruta 0.1.0a5 e BankaiRF 0.1.0a15.
- Todos os seis artefatos públicos PyPI a5 foram baixados e seus SHA256 comparados com os publicados. Hashes em `src/bankai_benchmark/release-verification.json`. Somente o wheel desta plataforma foi executado.
- `uv run pytest -q`: **88 testes passaram**, incluindo 11 casos de paridade clássico nativo/adaptador, quatro geradores, pesos/intensidades, interação com efeito marginal, cache, manifest incompatível, leitores históricos, relatórios v2 e topologias SMT/CPUs não contíguas/afinidade restrita/núcleos insuficientes/conjuntos aninhados até 16 CPUs.
- Smoke final: **16/16 fits passaram**, quatro perfis × quatro métodos, sem falhas; retomada sem modificar bytes ou mtime dos resultados. Tempo total do primeiro smoke final: 25,41 s, apenas evidência funcional local.
- Smoke selecionando explicitamente Bioinformática: **4/4 passaram**, incluindo retomada.
- Leitor histórico confirmou as 140 observações reais de qualidade a4 e sete métodos; relatório de conferência gerado somente em `/tmp`.
- `verify_campaign_archive.py verification/campaign-20261017`: **276 artefatos históricos verificados** pelos checksums originais.
- `cfn-guard`: **PASS** nas regras locais `amd_host` e `offline_capacity`: tipo AMD, 16/1 CPUs, capacidade zero, IMDSv2 e criptografia EBS. Regras e saída JSON anexas. Essas regras cobrem apenas as invariantes declaradas, não constituem auditoria abrangente de segurança/compliance.
- Testes offline de template, reservas ECS, placement e controlador: passaram na suíte. Template gerado com aproximadamente 4,7 KiB em JSON compacto, abaixo do limite inline de 51.200 bytes.
- `compileall` e `git diff --check`: passaram.

Pendentes: Docker não está instalado; aceitação Linux/container a5 não executada. `cfn-lint`/`cfn-validate` não disponíveis, portanto schema CloudFormation completo não validado. Validação de serviço AWS não executada. Topologia física, fabricante, afinidade Linux e VmHWM indisponíveis no smoke macOS, registrados explicitamente nos resultados. Não houve calibração extensa de recall nem campanha full.

`observations/` guarda manifests, resultados brutos e referências do smoke final, com hash da fonte usada. `final/report/` contém tabelas/placeholders provisórios. Logs locais estão neste diretório. Relatórios e medições a4 foram preservados; documentos anteriores estão em `docs/history/a4-20261017/`.

Para a etapa futura: instalar/usar Docker em Linux, executar `make docker-smoke`, validar o template com cfn-lint, verificar AMD com 16 núcleos físicos permitidos e conjuntos 1/2/4/8/16, registrar aceitação nova e digest da imagem. Revisar orçamento/duração antes de autorizar qualquer campanha. Usar IDs v2 novos; qualidade tem 80 fits e escala tem 100 fits independentes. Não reutilizar observações a4 nem o runner histórico scaling48. A redução de saturação e a melhora de recall seguem como hipóteses, sem comprovação por este smoke.
