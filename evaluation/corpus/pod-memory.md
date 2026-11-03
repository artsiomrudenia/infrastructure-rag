# Container memory exhaustion

## Symptoms
The last termination reason is OOMKilled with exit code 137. RSS exceeds the memory limit.
This is not a missing startup configuration.

## Checks
1. Compare container RSS and working set against its configured memory limit.
2. Inspect heap growth and recent traffic changes.

## Typical fix
Correct the memory leak or adjust the resource limit after measuring usage.
