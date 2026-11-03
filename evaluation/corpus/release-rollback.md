# Release error rate rollback

## Symptoms
HTTP 503 responses increase immediately after a deployment.
The new version fails readiness checks while the previous revision was healthy.

## Checks
1. Compare the error rate before and after the release.
2. Inspect readiness failures and deployment revision history.

## Typical fix
Roll back to the last healthy revision and investigate the release separately.
