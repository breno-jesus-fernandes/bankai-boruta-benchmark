# Orçamento dos pilotos ECS v2

O teto aprovado é R$400, com R$80 protegidos como reserva e R$320 como limite de alocação. O ledger AWS `bankai-budget/campaign-400-brl.json` foi reconciliado condicionalmente com o ledger v2 anterior: onze reservas de R$20 (R$220 comprometidos), preservando o histórico e sem reabrir slots gastos. Restam R$100 alocáveis. A aprovação anterior de R$400 já previa esse ledger sucessor; esta atualização incorporou os três slots registrados depois da migração inicial. As reservas são consumidas mesmo se uma tarefa for interrompida.

A próxima execução autorizada é uma calibração Industrial em tamanho real, até três horas em um host, com shutdown automático verificado antes de aumentar capacidade. O controller reservará R$60 atomicamente e manterá R$40 de alocação livre, além dos R$80 protegidos. A tabela tarifária consultada hoje indica cerca de R$15,32 por três horas incluindo EBS, IPv4 e 20% de contingência, com PTAX de R$5,0826 de 16/10; é uma estimativa de planejamento, não um limite AWS nem cobrança final. A política de preço/câmbio expira em 24/10/2026. A calibração anterior usou o protocolo antigo de quatro métodos e terminou incompleta após cinco de vinte trials; ela não será usada nas conclusões: [calibração interrompida](verification/v2-calibration-interrupted-20261018.md) e [cenários de custo](verification/v2-campaign-cost-plan-20261018.md).

A calibração antiga e a instância temporária r4 estão encerradas, sem capacidade ativa. O smoke r5 reutilizou a reserva aprovada de R$20 por transferência condicional do Fleet r4 vazio, mantendo o deadline original e sem adicionar reserva. Os 16 fits passaram e a instância foi terminada; o Fleet r5 está em zero. Evidência: [smoke ECS r5](verification/v2-r5-ecs-smoke-20261018.md). A frota da nova calibração será criada com capacidade desejada zero e uma única instância máxima.


## Candidato exato a7 (separado da referência a6)

A otimização a7/RF a16 tem [protocolo, diagnósticos, reprodução e critérios próprios](docs/exact-session-a7.md). O caminho novo permanece optativo, sem substituir pins, imagens, observações ou resultados históricos a6/a15. A validação AMD 1/4/16 workers e Industrial completo está pendente; esta atualização não alocou AWS nem alterou reservas.
