# Registry name resolution failure

## Symptoms
An image pull fails with NXDOMAIN or "no such host".
ImagePullBackOff occurs before any authentication request reaches the registry.
The registry IP cannot be resolved by the cluster DNS service.

## Checks
1. Resolve the registry hostname from the affected namespace.
2. Inspect CoreDNS upstream configuration and network access to the resolver.

## Typical fix
Correct the DNS record or restore resolver connectivity.
