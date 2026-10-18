# Single-host pilot deployment

The validated plan in `pilot-plan.json` runs the industrial quality suite with
the immutable image published by
[workflow 39059529475](https://github.com/breno-jesus-fernandes/bankai-boruta-benchmark/actions/runs/39059529475):

`642504869083.dkr.ecr.us-east-1.amazonaws.com/bankai-image-publisher-images@sha256:e1153cdb5d95fe72b42ae23c491bf30217055593d2de84a5ba6f65e23b19c4e4`

The CloudFormation CREATE change set was executed in `us-east-1`. The pilot stack is deployed:

- Stack: `bankai-pilot-20261017` (`CREATE_COMPLETE`)
- Change set: `pilot-review-20261017-v2`
- ARN: `arn:aws:cloudformation:us-east-1:642504869083:changeSet/pilot-review-20261017-v2/6f044df7-76ab-4815-9e09-1960c74b3eae`
- Ten resources were created: ECS cluster/capacity provider, association, three IAM roles, instance profile, launch template, Auto Scaling group and one-day CloudWatch log group.
- Auto Scaling group: `bankai-pilot-20261017-Fleet-UEWu3HaoKGNb`; current min=0, desired=0, max=1, with no instances.
- ECS cluster `pilot-20261017` has no active container instances.

The stack deployment created no EC2 instance and launched no ECS workload. A later `bankai-aws launch` action reserves BRL 20 in the shared ledger, arms and verifies the one-hour shutdown, then starts one `c7i.4xlarge` host and one industrial suite task. The campaign ledger allows up to BRL 160 in launch reservations and retains BRL 40. This time-based reservation and the USD20 monthly alert are monitoring controls; AWS does not enforce them as a hard account-wide cost cap.

Validation results are in `verification/aws-pilot-preflight.json`: local `cfn-lint` passed; two applicable selected AWS Guard rules passed, while the ECR scan rule was skipped because this plan creates no ECR repository; `cloudformation validate-template` succeeded; the service change set reached `CREATE_COMPLETE`; `describe-events` returned no `VALIDATION_ERROR` events. These checks do not validate runtime behavior or guarantee a total AWS cost. The stack was deployed with the local `bankai` profile, which currently authenticates as the account root user. A dedicated deployment identity is still needed before routine stack control or the paid launch.

AWS readback is recorded in `verification/aws-pilot-deployed.json`. No EC2 capacity has started. The next paid action is a separate one-host launch and still requires your approval.
