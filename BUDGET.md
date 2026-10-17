# R$200 campaign guard

The launch command is restricted to an idle, unsuspended, single-instance
c7i.4xlarge fleet in us-east-1. Provisioning leaves desired capacity zero.
The original five-host launch is disabled. The current launch is a quality
pilot on one dataset, not a complete paper campaign.

Before starting capacity, the controller:

1. Reserves R$20 against a R$160 campaign allowance in
   `s3://RESULT_BUCKET/bankai-budget/campaign-200-brl.json`.
2. Creates an Auto Scaling scheduled action one hour in the future, then reads
   it back to verify its time and all three zero capacity limits.
3. Starts one instance only after successful verification. Launch errors request
   immediate shutdown; the AWS-side scheduled action remains as backup.

The timer includes instance boot and task registration. AWS executes the action
independently of the controller. Setting maximum, minimum and desired capacity
to zero avoids replacement instances. ECS managed draining is disabled so long-running task draining does not
intentionally postpone instance termination. The root EBS volume is deleted on
termination. Completed pilots can leave the instance idle until the deadline;
run `destroy` to end early. A killed trial may lack a final result; previously
uploaded results remain. This pilot should not produce paper placeholders.

Each launch reserves the entire R$20 permanently, even after a failed API call,
short run or teardown. Eight reservations exhaust the R$160 allowance. There is
no automatic refund/reset command. S3 conditional writes prevent simultaneous
controllers from spending the same remaining allocation; a conflict aborts
rather than retrying a launch blindly. Reusing a fleet cannot extend its
deadline. Do not delete/edit the ledger or scheduled action, switch result
buckets, suspend scheduled scaling, or manually start other instances. These
operations bypass the policy. All launches in this campaign must use the same
bucket; the ledger is not an account-wide AWS spending limit.

R$40 remains outside the launch allowance for storage, networking, taxes,
exchange-rate movement and shutdown delays. The R$20 hourly reservation is a
conservative planning envelope, not a real-time billing measurement. AWS Pricing
API queried on 2026-10-17 returned Linux/shared/on-demand c7i.4xlarge in Northern
Virginia at US$0.714/hour. At an assumed exchange ceiling of R$6.50/USD plus
30%, compute is R$6.0333/hour. The launch policy expires on 2026-10-24 UTC and then blocks launches until
reviewed in code. Recheck pricing, FX and non-compute costs before launch; this policy is unsuitable if their combined rate approaches R$20/hour.
NAT gateways, public IPv4, endpoints and existing account resources are not
created or metered by this guard. ECR, logs and result objects need later cleanup.

This guard cannot guarantee the final AWS account bill stays below R$200.
Billing alerts are delayed; AWS scheduling/termination can also be delayed or
fail. Other account workloads are outside its scope. Keep billing alerts as a
secondary control, inspect the account after teardown, and retain the reserve.
No paid resources were started while implementing/testing this change.

The controller identity needs `s3:GetObject` and `s3:PutObject` on the ledger,
plus `autoscaling:DescribeAutoScalingGroups`, `DescribeScheduledActions`,
`PutScheduledUpdateGroupAction`, and `UpdateAutoScalingGroup` for this fleet,
in addition to existing deployment permissions. The container task role does
not need ledger access or permission to cancel shutdown. Access denial, corrupt
ledger, concurrent-write conflicts, invalid fleet geometry, or failed shutdown
verification blocks launch before capacity starts. Use a dedicated deployment
identity; do not grant these permissions to benchmark containers.

References: [scheduled actions](https://docs.aws.amazon.com/autoscaling/ec2/userguide/scheduled-scaling-create-scheduled-action.html)
and [AWS Budgets limitations](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html).
