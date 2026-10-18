# Orçamento v2 — planejamento offline

Nenhum recurso AWS foi iniciado nesta etapa. Os valores da campanha a4 são evidência histórica em [BUDGET a4](docs/history/a4-20261017/BUDGET.md), não uma estimativa para a AMD.

A campanha v2 tem 80 fits de qualidade e 100 de escala, além de warmups e referências downstream. As novas dimensões dobram N; o smoke local não permite estimar duração ou custo real. Não transportar tempos, preço de c7i ou alocações consumidas para uma campanha c7a.

Antes da campanha, obter cotação vigente c7a.4xlarge na região escolhida, câmbio, impostos, EBS, logs, tráfego e armazenamento; calcular limite por duração e manter reserva. Os limites existentes de `budget.py` são travas conservadoras, não orçamento calibrado do v2. Usar novo experiment ID e ledger aprovado, garantir encerramento automático e uma tarefa por host. Planos offline deixam DesiredCapacity=0.

A revisão de orçamento e a campanha paga ficam para uma etapa posterior. Nenhuma publicação de resultados ou imagens foi feita aqui.
