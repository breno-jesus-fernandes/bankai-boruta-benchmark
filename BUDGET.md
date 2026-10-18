# Orçamento do smoke ECS v2

O teto aprovado para o piloto ECS foi elevado para R$220. R$40 permanecem reservados, cada execução piloto consome irrevogavelmente R$20 e a política permite até nove reservas no total. O smoke autorizado é limitado a uma instância por até uma hora; uma ação agendada no Auto Scaling Group força min/max/desejado a zero como proteção adicional.

A imagem v2 foi publicada no ECR e a stack `bankai-paper-v2-a5-ecs-smoke` foi criada sem capacidade ativa. Antes de ligar a instância, a política local e o ledger S3 serão alinhados ao limite aprovado, uma reserva única será registrada e o desligamento automático será armado e verificado. O ledger conserva as reservas anteriores; falhas não devolvem valores automaticamente.

Este limite cobre somente o smoke ECS, não a campanha de qualidade ou escalabilidade. A c7a.4xlarge deve ser usada em `us-east-1`; planos offline mantêm capacidade desejada zero. O piloto não estima duração ou custo de campanha, nem valida recall em escala.
