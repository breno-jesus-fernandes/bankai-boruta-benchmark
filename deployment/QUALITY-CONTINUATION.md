# Remaining quality datasets without model polling

The user authorized continuation within the existing BRL200 campaign policy.
`scripts/continue_quality.py` runs Crédito, Bioinformática, then Cibersegurança
sequentially. Industrial is already complete. Thread scaling remains a separate
campaign after quality review.

The controller reuses the original cluster, task definition, IAM roles, pinned
launch-template version, and immutable image. Tasks use EC2 launch type; new
zero-capacity Auto Scaling groups join the same cluster. No CloudFormation
template or benchmark implementation is changed. Original experiment IDs and
the shared immutable 140-trial quality manifest remain intact.

Each dataset uses a fresh ASG, reserves BRL20 in the existing conditional-write
S3 ledger, and verifies a one-hour AWS-side shutdown **before** increasing
desired capacity. There is at most one campaign host at a time. Including the
Industrial reservation, the three planned launches reserve BRL80 total; the
ledger still limits all launches to BRL160 and keeps BRL40 reserved. Reservations
are conservative allocations, not measured AWS charges or an account-wide cap.
Hosts are terminated early when a task finishes. Zero-capacity ASGs are retained
for audit; they can be removed in explicit later teardown.

Failures, incomplete results, expired deadlines, credential errors, budget
rejections, or an existing attempted dataset halt progression. There is no
automatic paid retry and no deadline extension. AWS-side shutdown stays armed
if the local controller stops. A local flock prevents duplicate controllers.

The process polls AWS every minute, updates `reports/quality-monitor/status.txt`,
and appends a very short report to `updates.txt` every 30 minutes and on phase
changes/completion/errors. Optional macOS desktop notifications use the same
text. Notifications depend on macOS settings; the local file is authoritative.
No OpenAI/Codex/model API is used by this process. Automated reports do not
appear in the chat. AWS requests, storage, and compute can still be billed.

The local machine must stay on and connected. `caffeinate -i` prevents idle sleep
while this process runs; it does not prevent manual sleep or power loss. The
controller runs as a detached local process with no automatic restart. It
survives the chat turn ending; it does not survive a computer restart/logout.
Credentials remain in the configured AWS profile and are not embedded in code.

Runtime state, downloaded results, aggregate reports, and process logs are under
`reports/quality-monitor/` (gitignored). Original Industrial artifacts are also
committed under `verification/pilot-20261017/`. All raw results remain in S3.

```sh
cat reports/quality-monitor/status.txt
tail reports/quality-monitor/updates.txt
ps -p $(cat reports/quality-monitor/process.pid) -o pid,state,etime,command
```

Stopping the local agent alone does not terminate EC2 immediately. The AWS
one-hour schedule remains the fallback; to stop early, zero the active ASG and
stop its ECS task, using the names in `controller.json`. Do not restart a prior
paid attempt without reviewing its reservation and results.
