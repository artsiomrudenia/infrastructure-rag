# Prometheus High Error Rate Alert
#prometheus #monitoring #alerts

## Symptoms
Error rate alert fires immediately after new release.

## Checks
1. Compare request error ratio before and after deployment.
2. Inspect service logs for HTTP 5xx spikes.
3. Check dependency timeout metrics.

## Typical fix
Rollback release if spike correlates with deployment and confirm metric normalization.
