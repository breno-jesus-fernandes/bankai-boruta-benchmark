# QUALITY-CONTINUATION — protocolo v2

O runbook anterior pertence à campanha a4: [arquivo histórico](../docs/history/a4-20261017/deployment-QUALITY-CONTINUATION.md). Não aplicar contagens, baseline reutilizado, preço, task definition ou digest daquela campanha ao v2.

Use [infraestrutura v2](README.md), [protocolo](../README.md) e [validação local](../VERIFICATION.md). Qualidade tem 60 fits a 16 núcleos; escala tem 75 fits novos a 1/2/4/8/16 núcleos e baseline próprio de uma CPU. Alvo AMD c7a.4xlarge, uma tarefa por host, 16 CPUs e 28 GiB reservados. Planos permanecem com capacidade desejada zero. Campanha, publicação e orçamento real aguardam validação Linux/container e etapa posterior.
