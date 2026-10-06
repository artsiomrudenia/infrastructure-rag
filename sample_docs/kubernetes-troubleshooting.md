# Kubernetes Pod CrashLoopBackOff Troubleshooting
#kubernetes #troubleshooting #runbook

## Symptoms
Pod enters `CrashLoopBackOff` and restart count keeps increasing.

## Checks
1. Run `kubectl describe pod <pod>` and inspect recent events.
2. Run `kubectl logs <pod> --previous` to get crash output.
3. Verify ConfigMap and Secret keys are present.

## Typical fix
If a bad deployment introduced invalid env vars, rollback the deployment and compare manifests.
