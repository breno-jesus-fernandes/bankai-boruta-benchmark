# PUBLISHING — protocolo v2

O runbook anterior pertence à campanha a4: [arquivo histórico](../docs/history/a4-20261017/deployment-PUBLISHING.md). Não aplicar contagens, baseline reutilizado, preço, task definition ou digest daquela campanha ao v2.

Use [infraestrutura v2](README.md), [protocolo](../README.md) e [validação local](../VERIFICATION.md). Protocolo r5: qualidade tem 80 fits a 16 núcleos; escala tem 60 fits novos em 4/8/16 núcleos e baseline próprio de quatro CPUs. Alvo AMD c7a.4xlarge, uma tarefa por host, 16 CPUs e 28 GiB reservados. Planos offline mantêm capacidade desejada zero. A aceitação Linux/container r5 passou; publique a imagem imutável pelo workflow de publicação e registre o digest.


## Candidato exato a7 (separado da referência a6)

A otimização a7/RF a16 tem [protocolo, diagnósticos, reprodução e critérios próprios](../docs/exact-session-a7.md). O caminho novo permanece optativo, sem substituir pins, imagens, observações ou resultados históricos a6/a15. A validação AMD 1/4/16 workers e Industrial completo está pendente; esta atualização não alocou AWS nem alterou reservas.
