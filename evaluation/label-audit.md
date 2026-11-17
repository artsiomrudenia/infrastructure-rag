# Independent relevance-label audit

Reviewed 2026-11-17 against every Markdown runbook in `evaluation/corpus/`.
Relevance was reasoned from what each source document actually addresses, then
compared with the existing labels. A path is relevant only when its runbook contains
information that addresses the query; a shared term by itself is insufficient.

## Legacy dataset

| Query ID | Independently supported path(s) | Review |
|---|---|---|
| `dev-restart-en` | `pod-restarts.md` | Missing startup configuration and CrashLoopBackOff symptoms match. |
| `dev-restart-ru` | `pod-restarts.md` | Startup command and CrashLoopBackOff checks match. |
| `dev-restart-paraphrase` | `pod-restarts.md` | Missing settings file at process launch matches. |
| `dev-restart-cross` | `pod-restarts.md` | Repeated restarts caused by a missing config file match. |
| `dev-auth-en` | `registry-auth.md` | The identifier is explicitly listed as an authentication symptom. |
| `dev-auth-ru` | `registry-auth.md` | HTTP 401 during image pull matches. |
| `dev-capacity-short` | `disk-capacity.md` | `df -i` is explicitly prescribed for inode exhaustion. |
| `dev-capacity-ru` | `disk-capacity.md` | ENOSPC is an explicit symptom. |
| `dev-tls-en` | `tls-expiry.md` | Expired-certificate handshake failure matches. |
| `dev-tls-short` | `tls-expiry.md` | Topical association only: `TLS` does not specify an issue or task. Retained as a legacy short-term probe; not a strict answerability label. |
| `dev-tls-cross` | `tls-expiry.md` | Expired certificate preventing a secure connection matches. |
| `dev-multiple` | `registry-auth.md`, `tls-expiry.md` | The question explicitly combines expired registry credentials and TLS certificates. |
| `dev-unknown-en` | *(none)* | Quantum entanglement is not covered. |
| `dev-unknown-ru` | *(none)* | Gardening is not covered. |
| `dev-nearmiss` | *(none)* | Registry image retention/garbage collection is distinct from authentication and DNS. |
| `dev-nearmiss-ru` | *(none)* | Certificate pricing is not covered by the expiration runbook. |
| `test-memory-en` | `pod-memory.md` | OOMKilled and exit code 137 are explicit symptoms. |
| `test-memory-ru` | `pod-memory.md` | OOMKilled and RSS growth match. |
| `test-memory-cross` | `pod-memory.md` | Exceeding a memory limit and forced termination match. |
| `test-memory-paraphrase` | `pod-memory.md` | Heap growth beyond the allowed allocation matches. |
| `test-dns-en` | `registry-dns.md` | NXDOMAIN/no-such-host during image pull matches. |
| `test-dns-ru` | `registry-dns.md` | CoreDNS and NXDOMAIN are directly covered. |
| `test-dns-short` | `registry-dns.md` | Topical association only: `IP?` does not identify a lookup task. Retained as a legacy short-term probe; not strict answerability evidence. |
| `test-io-short` | `disk-io.md` | Topical association only: `IO?` does not specify latency, queue depth, or another task. Retained as a legacy short-term probe; not strict answerability evidence. |
| `test-io-ru` | `disk-io.md` | High IO latency and disk queue match. |
| `test-rollback-en` | `release-rollback.md` | HTTP 503/readiness failure after deployment matches. |
| `test-rollback-cross` | `release-rollback.md` | Increased post-release errors and reverting the version match. |
| `test-multiple` | `registry-dns.md`, `disk-io.md` | Registry name resolution and storage queue latency are both directly covered. |
| `test-unknown-en` | *(none)* | Ocean salinity/coral biodiversity is not covered. |
| `test-unknown-ru` | *(none)* | Baking is not covered. |
| `test-nearmiss` | *(none)* | Storage encryption-key rotation is not covered by capacity or IO guidance. |
| `test-nearmiss-ru` | *(none)* | DNS billing is not covered by name-resolution troubleshooting. |

Result: 29 labels are supported under the task-relevance rubric. The remaining
three are retained for historical comparison, but their one-token prompts do not
support an independent task-level relevance judgment. Exclude their individual
outcomes from answerability claims. The legacy `queries.json` was not changed, so
its established dev/test contents and fingerprints remain stable.

## Fresh holdout

`queries-holdout.json` contains 16 independently authored questions: 12 answerable
and four unanswerable. Each answerable label was checked against the relevant
runbook section; each empty label was checked against the complete eight-document
corpus, including near misses. Questions specify an operational intent, unlike the
three underspecified legacy probes. IDs, normalized question text, and family names
are checked for overlap with the legacy set in `tests/test_evaluation.py`.

No holdout ranking was used to write its labels or choose settings. Regression tests
validate the dataset and split using a separate synthetic smoke query; they do not
score this holdout. Freeze retriever/configuration choices on dev before its first
run. Any change informed by its detailed results requires another fresh holdout.