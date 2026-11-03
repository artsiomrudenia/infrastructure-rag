# Storage latency investigation

## Symptoms
IO latency and disk queue depth rise while capacity remains available.
Requests stall while waiting for storage. IOPS reach the volume limit.

## Checks
1. Measure IO wait, queue depth, and volume latency.
2. Compare IOPS with provisioned throughput.

## Typical fix
Reduce competing IO or provision storage throughput appropriate to the workload.
