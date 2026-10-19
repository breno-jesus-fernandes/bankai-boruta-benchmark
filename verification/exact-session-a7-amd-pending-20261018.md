# Estado da validação AMD a7 — 18/10/2026

BankaiRF 0.1.0a16 e Bankai Boruta 0.1.0a7 estão publicados no PyPI. A PR do
benchmark #8 foi mesclada em `7b9f5d1ff1a36f642aa6a274213512100a80c70a`.
Os resultados locais e do Linux hospedado continuam registrados em
[`exact-session-a7-local/README.md`](exact-session-a7-local/README.md); não são
substitutos da medição no AMD.

## Conta e autorização

Leitura da conta AWS `642504869083` em 18/10/2026:

- Nenhuma instância EC2 em execução; as frotas Auto Scaling consultadas estão
  com capacidade desejada zero.
- O ledger `s3://bankai-benchmark-bootstrap-results-ku2wdx1kzzqb/bankai-budget/campaign-400-brl.json`
  contém 14 reservas de R$20, total de R$280. Do teto alocável de R$320 restam
  R$40; a reserva protegida de R$80 permanece intacta.
- Três slots já estão reservados à calibração `bankai-paper-v2-a6-amd16-r5-cal-industrial`.
  Eles não foram transferidos para a campanha independente a7.
- O AWS Budgets guard reportou US$3,538 de gasto contabilizado e US$2,545 de
  previsão, sob limite mensal de US$40. Cost Explorer ainda marca o período como
  estimado.

A campanha de aceitação definida em `docs/exact-session-a7.md` contém 90 pares
de comparação (cada par executa a6 e a7), antes de qualquer repetição adicional
por host. Os R$40 livres cobrem no máximo dois slots de uma hora segundo a regra
do ledger, portanto não autorizam o grid completo. A política de preço e câmbio
expira em 24/10/2026. Nenhum recurso foi criado, nenhum slot foi reservado e o
ledger permaneceu inalterado nesta atualização.

## Próxima execução

Antes da campanha completa, preparar e revisar um digest de imagem exclusivo
para `exact-session-a7-v1`, estimar sua duração em um piloto representativo,
consultar preços e câmbio novamente e definir um orçamento que cubra o grid com
shutdown AWS verificável. Até isso estar coberto, manter a sessão opt-in e
reportar a validação AMD como pendente. Não misturar seus artefatos com o
protocolo ou o diretório histórico a6.
