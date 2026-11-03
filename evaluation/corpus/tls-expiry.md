# TLS certificate expiration

## Symptoms
HTTPS clients report CERT_HAS_EXPIRED. The TLS handshake fails after the certificate notAfter date.
The application itself is healthy.

## Checks
1. Inspect the certificate expiration date and full certificate chain.
2. Verify that the ingress references the renewed secret.

## Typical fix
Renew the certificate and reload the ingress configuration.
