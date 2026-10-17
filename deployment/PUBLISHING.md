# Dedicated image publisher

`publisher.json` proposes three resources in `us-east-1`: GitHub's IAM OIDC
provider, an IAM role and ECR repository `bankai-image-publisher-images`.
The prepared CREATE change set is `publisher-review-20261017` in stack
`bankai-image-publisher`. It has not been executed. The review placeholder is
`REVIEW_IN_PROGRESS`; do not call create-stack again against that name.

The role accepts only GitHub subject
`repo:breno-jesus-fernandes@32203685/bankai-boruta-benchmark@1423557673:ref:refs/heads/main`, with
`sts.amazonaws.com` audience. No AWS access keys or user passwords are created.
This is a dedicated **image publisher**, not a deployment administrator. It has
no EC2, ECS, Auto Scaling, S3, IAM or budget-management permission. The local
controller profile still needs a separate dedicated identity before paid runs.

Docker push uses the documented ECR actions, scoped to this repository, plus
`DescribeImages` to resolve the resulting digest. `GetAuthorizationToken` is the
only action using `Resource: "*"`, as required by ECR. This policy comes from
Docker's named ECR operations, not analysis of the benchmark Python callers;
the broad runtime SDK baseline remains unused. Sources:

- https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-push-iam.html
- https://servicereference.us-east-1.amazonaws.com/v1/ecr/ecr.json
- https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-idp_oidc.html

Validation: cfn-lint; five selected AWS Guard registry rules; Access Analyzer
(no findings); IAM simulator; account-aware CREATE change set (no validation
errors). The simulator separately checks global token authorization and
repository-specific uploads. Upload to another repository and sampled compute,
S3 and IAM actions are denied. It does not exercise real GitHub OIDC trust;
the first publication must verify the actual assumed-role caller and push.
Evidence is `verification/aws-publisher-preflight.json`.

After explicit approval, execute the existing change set, wait for
CREATE_COMPLETE, and read `RoleArn`/`RepositoryName` outputs:

```sh
AWS_PROFILE=bankai aws cloudformation execute-change-set --region us-east-1 \
  --stack-name bankai-image-publisher --change-set-name publisher-review-20261017
AWS_PROFILE=bankai aws cloudformation describe-stacks --region us-east-1 \
  --stack-name bankai-image-publisher --query 'Stacks[0].Outputs'
```

Set repository variable `AWS_IMAGE_PUBLISH_ROLE` to the exact RoleArn output.
The manual `publish-image.yml` workflow runs only on main. It executes tests,
checks the verified public release, builds Linux amd64, and runs Linux smoke
inside that image before acquiring temporary AWS credentials. It pushes that
same image with an immutable commit/run/attempt tag, resolves its digest and
saves `published-image.json` as a workflow artifact. Actions are pinned to
source commits. Image publication starts no benchmark EC2 capacity.

ECR uses AES256 encryption, immutable tags and basic scan-on-push. Basic scanning
adds no scanning subscription; stored image bytes incur ordinary ECR storage
charges. No enhanced Inspector scanning is enabled by this template. Remove
unused images explicitly after the campaign while preserving the image digest
used for measured results. Keep total ancillary charges within the reserve.

This template creates the first GitHub OIDC provider in this account (read-only
inventory returned none). Do not deploy a duplicate if another provider is
created concurrently; review the change set again instead.

The repository OIDC API returned `use_immutable_subject=true` and the prefix
above. The first publication exposed a mismatch with the legacy name-only
subject. The corrected trust uses `GitHubSubjectPrefix` discovered from
`gh api repos/breno-jesus-fernandes/bankai-boruta-benchmark/actions/oidc/customization/sub`.
It does not opt out of immutable subjects or add a wildcard. New/renamed GitHub
repositories after July 15, 2026 can use this format:
https://github.blog/changelog/2026-04-23-immutable-subject-claims-for-GitHub-actions-oidc-tokens/
