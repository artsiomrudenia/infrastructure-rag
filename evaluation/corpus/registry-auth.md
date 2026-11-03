# Registry authentication failure

## Symptoms
An image pull returns HTTP 401 Unauthorized or ERR_AUTH_42.
ImagePullBackOff follows an expired registry credential. DNS resolution succeeds.

## Checks
1. Verify the imagePullSecrets reference and credential expiration.
2. Check permission to read the requested image repository.

## Typical fix
Rotate the registry credential and update the pull secret.
