# Approved Industrial scaling at 4, 8 and reused 16 threads

The user reduced the campaign on 2026-10-18 UTC to new measurements at **4 and
8 threads**, retaining five seeds (42–46) and all seven configurations.
This is 70 new measured trials plus 28 discarded warmups. The 35 already
measured Industrial quality trials at 16 threads are reused in the comparison;
no 16-thread fit, warmup, or synthetic replacement is scheduled. Threads 1 and 2
are not part of this campaign.

The queued controller in `scripts/scaling48.py` waits for all 140 quality trials
to succeed and for the previous host to terminate. It then starts one
`c7i.4xlarge` using the original pinned launch template and immutable image.
The ECS task definition adds a versioned inline Python entry point that restricts
the existing scaling grid to 4/8 threads, processing 8-thread trials first.
The worker, selectors, dataset generators and installed package files are not
changed. The exact wrapper and its SHA256 are recorded in the script/state.
The same full-size Industrial profile, seeds, timing, memory and affinity rules
therefore apply. S3 prefixes remain `pilot-20261017-quality/` (original data)
and `pilot-20261017-scaling/` (new trials and a restricted immutable manifest).

Three nonrefundable BRL20 reservations fund a **maximum three-hour** task. All
reservations and the AWS-side shutdown readback must succeed before paid
capacity starts. At the recorded BRL100 prior allocation, this consumes the
remaining BRL60 launch allowance and leaves BRL40 outside it. The three-hour
limit includes boot/registration; it is a spending guard, not a prediction that
all 70 measurements will finish. Completed results persist if it times out;
there is no automatic retry, deadline extension, or further spending.

The original one-hour policy remains the default for quality pilots. This
three-hour bound applies only to this reduced scaling plan. The existing
Bioinformatica extension and its additional BRL20 reservation remain unchanged.
The ledger is not the AWS bill or a guaranteed account-wide cap.

`thread_scaling.csv` reports medians, Q1, Q3 and IQR for 4/8/16 threads. Speedups
are paired by seed **relative to four threads** (`T4/Tt`). The reported relative
efficiency is `speedup/(t/4)`, not conventional one-thread parallel efficiency.
`origins.json` points each reused observation to its original quality experiment
and trial ID without changing its suite, configuration hash or raw data.

Reusing measurements is conditional on matching source/dependency/image/CPU
topology provenance, full dataset metadata per seed, and requested CPU affinity.
Any mismatch aborts the comparison and stops progression. Incomplete cells and
failures remain visibly provisional and never become zero-valued timings.
The raw 16-thread archive is committed under `verification/pilot-20261017/input`.

The detached controller uses no model API. Keep the local Mac on and connected.
Reports/notifications follow the existing 30-minute convention. Runtime data:

```sh
cat reports/scaling48-monitor/status.txt
tail reports/scaling48-monitor/updates.txt
cat reports/scaling48-monitor/report/summary.md
```

Read the `controller.json` files for ECS/ASG identities and AWS shutdown times.
Raw new results remain in S3 if the local monitor exits. No new campaign is
automatically launched after this reduced scaling task.
