# Single-host pilot deployment

The validated plan in `pilot-plan.json` runs the industrial quality suite with
the immutable image published by
[workflow 39059529475](https://github.com/breno-jesus-fernandes/bankai-boruta-benchmark/actions/runs/39059529475):

`642504869083.dkr.ecr.us-east-1.amazonaws.com/bankai-image-publisher-images@sha256:e1153cdb5d95fe72b42ae23c491bf30217055593d2de84a5ba6f65e23b19c4e4`

The CloudFormation CREATE change set is ready in `us-east-1`:

- Stack: `bankai-pilot-20261017` (`REVIEW_IN_PROGRESS`)
- Change set: `pilot-review-20261017-v2`
- ARN: `arn:aws:cloudformation:us-east-1:642504869083:changeSet/pilot-review-20261017-v2/6f044df7-76ab-4815-9e09-1960c74b3eae`
- Change set status: `CREATE_COMPLETE`, execution status `AVAILABLE`
- Ten resources will be added: ECS cluster/capacity provider, association, three IAM roles, instance profile, launch template, Auto Scaling group and one-day CloudWatch log group.

The Auto Scaling group starts at minimum 0, desired 0 and maximum 1. Executing this change set creates the pilot control plane, but starts no EC2 instance. A later `bankai-aws launch` action reserves BRL 20 in the shared ledger, arms and verifies the one-hour shutdown, then starts one `c7i.4xlarge` host and one industrial suite task. The campaign ledger allows up to BRL 160 in launch reservations and retains BRL 40. This time-based reservation and the USD20 monthly alert are monitoring controls; AWS does not enforce them as a hard account-wide cost cap.

Validation results are in `verification/aws-pilot-preflight.json`: local `cfn-lint` passed; two applicable selected AWS Guard rules passed, while the ECR scan rule was skipped because this plan creates no ECR repository; `cloudformation validate-template` succeeded; the service change set reached `CREATE_COMPLETE`; `describe-events` returned no `VALIDATION_ERROR` events. These checks do not validate runtime behavior or guarantee a total AWS cost. The change set was created with the local `bankai` profile, which currently authenticates as the account root user. A dedicated deployment identity is still needed before routine stack control or the paid launch.

The CloudFormation workflow requires explicit approval before executing this change set because execution changes live AWS infrastructure. The exact operation is:

```sh
aws --profile bankai --region us-east-1 cloudformation execute-change-set \
  --change-set-name arn:aws:cloudformation:us-east-1:642504869083:changeSet/pilot-review-20261017-v2/6f044df7-76ab-4815-9e09-1960c74b3eae
```

If this CREATE change set is not used, deleting it alone leaves the stack in `REVIEW_IN_PROGRESS`; remove both the change set and that review-only stack before creating another one with the same stack name.
