# Dedicated image publisher

`publisher.json` provisions GitHub's IAM OIDC provider, a narrowly scoped IAM
role and ECR repository `bankai-image-publisher-images` in `us-east-1`. The
`bankai-image-publisher` stack is deployed and `UPDATE_COMPLETE` after aligning
its trust with GitHub's immutable subject claim. The role ARN is
`arn:aws:iam::642504869083:role/bankai-image-publisher-Publisher-UiA3IL8kWojx`.

The role accepts only GitHub subject
`repo:breno-jesus-fernandes@32203685/bankai-boruta-benchmark@1423557673:ref:refs/heads/main`, with
`sts.amazonaws.com` audience. No AWS access keys or user passwords are created.
This is a dedicated **image publisher**, not a deployment administrator. It has
no EC2, ECS, Auto Scaling, S3, IAM or budget-management permission. A separate
dedicated identity is needed to deploy the pilot.

Docker push uses the documented ECR actions, scoped to this repository, plus
`DescribeImages` to resolve the resulting digest. `GetAuthorizationToken` is the
only action using `Resource: "*"`, as required by ECR. This policy comes from
Docker's named ECR operations, not analysis of the benchmark Python callers;
the broad runtime SDK baseline remains unused. Sources:

- https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-push-iam.html
- https://servicereference.us-east-1.amazonaws.com/v1/ecr/ecr.json
- https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html

Validation before deployment: cfn-lint; five selected AWS Guard registry rules;
Access Analyzer (no findings); IAM simulator; account-aware CREATE change set
(no validation errors). The simulator separately checks global token
authorization and repository-specific uploads. Upload to another repository and
sampled compute, S3 and IAM actions are denied. It does not exercise real GitHub
OIDC trust; the first publication verified the actual assumed-role caller and
push. Evidence is `verification/aws-publisher-preflight.json`.

The deployed repository URI is
`642504869083.dkr.ecr.us-east-1.amazonaws.com/bankai-image-publisher-images`.
The GitHub repository variable `AWS_IMAGE_PUBLISH_ROLE` points to the role ARN.
Stack and repository readback are recorded in
`verification/aws-publisher-deployed.json`.

The manual `publish-image.yml` workflow runs only on main. It executes the
suite, checks the verified public release, builds Linux amd64, and runs Linux
smoke inside that image before acquiring temporary AWS credentials. It pushes
that same image with an immutable commit/run/attempt tag, resolves its digest
and saves `published-image.json` as a workflow artifact. Actions are pinned to
source commits.

The first publication completed successfully in GitHub Actions run
[`39059529475`](https://github.com/breno-jesus-fernandes/bankai-boruta-benchmark/actions/runs/39059529475)
from source revision `e11befc25ceb16e0367b965df8f17c6f7a6890ed`. The workflow
assumed the dedicated publisher role in account `642504869083` and published
immutable image
`642504869083.dkr.ecr.us-east-1.amazonaws.com/bankai-image-publisher-images@sha256:e1153cdb5d95fe72b42ae23c491bf30217055593d2de84a5ba6f65e23b19c4e4`.
The tag is
`e11befc25ceb16e0367b965df8f17c6f7a6890ed-39059529475-1`. ECR readback matched
the digest and tag. Evidence is in `verification/aws-image-published.json`.

ECR uses AES256 encryption, immutable tags and basic scan-on-push. Basic
scanning adds no scanning subscription; stored image bytes incur ordinary ECR
storage charges. No enhanced Inspector scanning is enabled by this template.
Remove unused images explicitly after the campaign while preserving the image
digest used for measured results. Keep total ancillary charges within the
reserve.

The pilot stack remains a plan only. No benchmark EC2 capacity has been
deployed or started. The campaign guard reserves BRL 20 per launch, up to BRL
160 operating allowance and BRL 40 reserve; this is a time-based reservation,
not a hard account-wide AWS spending cap.

The repository OIDC API returned `use_immutable_subject=true` and the prefix
above. The initial publication attempt exposed a mismatch with the legacy
name-only subject. The corrected trust uses `GitHubSubjectPrefix` discovered
from `gh api repos/breno-jesus-fernandes/bankai-boruta-benchmark/actions/oidc/customization/sub`.
It does not opt out of immutable subjects or add a wildcard. New or renamed
GitHub repositories after July 15, 2026 can use this format:
https://github.blog/changelog/2026-04-23-immutable-subject-claims-for-GitHub-actions-oidc-tokens/
