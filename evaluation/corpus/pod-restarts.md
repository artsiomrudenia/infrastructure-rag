# Pod restart investigation

## Symptoms
The Kubernetes workload enters CrashLoopBackOff. The restart counter increases.
The container exits immediately because its startup command refers to a missing configuration file.

## Checks
1. Use kubectl logs --previous to read the last container exit.
2. Compare the mounted configuration path with the startup command.

## Typical fix
Restore the missing configuration and restart the workload.
