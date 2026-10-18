# Aceitação Linux/container — protocolo r4 — 2026-10-18

A aceitação do container r4 passou no GitHub Actions em [39151871780](https://github.com/breno-jesus-fernandes/bankai-boruta-benchmark/actions/runs/39151871780), no commit `b84fc4054efe026dc92f806ef02f4fdb9ff938ea`. O workflow executou a suíte Python, gate do release público, build amd64 e `scripts/verify_linux.py`. O verificador confirmou 12/12 casos (quatro perfis × três métodos), Linux VmHWM, afinidade e topologia verificadas e caminho nativo Rust do `bankai_native_extra_tree`.

A imagem imutável publicada é `642504869083.dkr.ecr.us-east-1.amazonaws.com/bankai-image-publisher-images@sha256:838231861df859a45936f531e8880fd212049ac00a775091721f948efa01c693`. O digest e a evidência estão registrados em `src/bankai_benchmark/release-verification.json`.

Esta etapa valida o smoke funcional no container Linux; ele usa quatro iterações e não exercita o early stopping. O smoke ECS anterior e a calibração interrompida pertencem ao protocolo r2. O ledger de R$240 tem dez reservas alocadas e nenhuma livre; não foi iniciado host ECS nem teste pago r4. O próximo teste deve usar este digest, um manifesto `paper-v2-a5-amd16-r4` e uma nova reserva aprovada.
