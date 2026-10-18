# Orçamento do smoke ECS v2

O teto aprovado para o piloto ECS foi elevado para R$220. R$40 permanecem reservados, cada execução piloto consome irrevogavelmente R$20 e a política permite até nove reservas no total. A nona reserva cobriu um único smoke de qualidade, limitado a uma instância por até uma hora. O resultado e a validação estão em [smoke ECS de 18/10/2026](verification/v2-ecs-smoke-20261018.md).

A imagem v2 foi publicada no ECR e a stack `bankai-paper-v2-a5-ecs-smoke` foi criada sem capacidade inicial. Antes da ativação, o ledger S3 foi atualizado condicionalmente de R$200 para R$220, preservando suas oito reservas anteriores; a reserva nova foi registrada e a ação agendada de desligamento foi verificada. O teste terminou em 39 segundos com código zero e a capacidade foi imediatamente reduzida a zero. O ledger conserva reservas mesmo quando uma execução termina; falhas não devolvem valores automaticamente.

Este limite cobriu somente o smoke ECS, não a campanha de qualidade ou escalabilidade. O smoke confirma a execução no host AMD `c7a.4xlarge`; seus dados reduzidos não estimam duração, custo ou recall da campanha completa. Planos offline mantêm capacidade desejada zero. A stack continua provisionada, sem instâncias ativas.
