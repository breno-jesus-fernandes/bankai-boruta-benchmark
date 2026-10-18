# SCALING48 — protocolo v2

O runbook anterior pertence à campanha a4: [arquivo histórico](../docs/history/a4-20261017/deployment-SCALING48.md). Não aplicar contagens, baseline reutilizado, preço, task definition ou digest daquela campanha ao v2.

Use [infraestrutura v2](README.md), [protocolo](../README.md) e [validação local](../VERIFICATION.md). Protocolo r5: qualidade tem 80 fits a 16 núcleos; escala tem 60 fits novos em 4/8/16 núcleos e baseline próprio de quatro CPUs. Alvo AMD c7a.4xlarge, uma tarefa por host, 16 CPUs e 28 GiB reservados. Planos offline mantêm capacidade desejada zero. `scripts/scaling48.py` segue restrito ao leitor/controlador histórico a4; não use seus dados no r5.
