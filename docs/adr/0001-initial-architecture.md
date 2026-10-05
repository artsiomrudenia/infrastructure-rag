# ADR-0001: Initial Architecture

- Date: 05/10/2026
- Status: Accepted

## Context

The project needs a public baseline for infrastructure-focused RAG services and repeatable Kubernetes delivery.

## Decision

Implement a minimal FastAPI service and provide both raw manifests and Helm deployment options.

## Consequences

- Reusable baseline for future RAG modules
- Predictable CI checks (tests + image build)
