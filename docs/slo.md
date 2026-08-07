# Initial service probes and SLO

This document defines the Phase 1 operational contract. These are initial objectives until
production telemetry provides a baseline; changing them requires an explicit documentation and
deployment review.

## Probe contract

All probes are unauthenticated, exact-path, `GET`-only HTTP endpoints. Responses are JSON and
include `Cache-Control: no-store`. They expose no credentials, hostnames, database names, or error
details.

| Path | Meaning | Success | Failure | Intended consumer |
|------|---------|---------|---------|-------------------|
| `/livez` | The MCP process and event loop can answer HTTP. No dependency calls are made. | `200 {"status":"alive"}` | Connection failure or timeout | Process liveness/restart controller |
| `/readyz` | The configured ArangoDB database accepts a read-only properties request. | `200`, `status: "ready"` | `503`, `status: "not_ready"`, or timeout | Traffic admission and container health |
| `/healthz` | Deprecated compatibility alias for `/readyz`. | Identical status and body to `/readyz` | Identical status and body to `/readyz` | Existing integrations only |

`/healthz` also returns `Deprecation: @1785888000` (2026-08-05 00:00:00 UTC, using the RFC 9745
Structured Field Date format) and a successor `Link` to `/readyz`. No removal date is set in Phase
1. New clients must not adopt it.

Readiness is intentionally false before the connector is initialized and whenever ArangoDB is
unavailable. Liveness remains true during an ArangoDB outage so an orchestrator can distinguish a
dependency incident from a wedged MCP process. A readiness check is read-only and runs outside the
async event-loop thread.

## Container timing

The Docker image and Compose service use `/readyz`, not `/livez`, for container health:

- interval: 10 seconds
- HTTP client timeout: 2 seconds
- container health timeout: 3 seconds
- startup grace: 15 seconds
- unhealthy threshold: 5 consecutive failures

Platforms with separate liveness and readiness controls should use `/livez` for liveness and
`/readyz` for readiness. A platform restart policy must not use `/readyz`: restarting the MCP
process does not repair an ArangoDB outage.

## Initial SLOs

The readiness availability SLI is:

`eligible /readyz observations returning HTTP 200 / all eligible /readyz observations`

An observation is eligible after the 15-second startup grace while at least one MCP replica is
intended to serve traffic. HTTP `503`, connection errors, and timeouts count as failures. Planned
maintenance is not excluded. Periods intentionally scaled to zero produce no observations.

- **Readiness availability objective:** at least **99.9%** over a rolling 30-day window.
- **Readiness latency objective:** at least **99%** of eligible `/readyz` observations complete
  within 1 second over a rolling 30-day window.

The 99.9% availability objective permits approximately 43 minutes 50 seconds of failed readiness
in a 30-day window. Alerting should use both a fast burn (1-hour window) and a slow burn (6-hour
window); exact alert thresholds are deployment-specific and are not implemented in Phase 1.

`/livez` is an operational signal, not the service-availability SLI. Any liveness failure should be
treated as a process incident, while readiness failures consume the service error budget because
the instance cannot safely receive MCP traffic.
