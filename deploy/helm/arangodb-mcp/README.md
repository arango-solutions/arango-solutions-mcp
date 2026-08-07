# ArangoDB MCP Helm chart

This is the supported Kubernetes deployment for the ArangoDB MCP Server. It deploys the
server only; connect it to a separately operated ArangoDB deployment through `arango.hosts`.
Kubernetes 1.27 or newer is supported.

## Install with an existing Secret

Production installations should use an existing Kubernetes Secret, an External Secrets
operator, or a CSI secret provider. The chart never contains real default credentials and
does not create a Secret unless `secrets.create.enabled=true`.

Legacy bearer mode requires the ArangoDB password and an independent MCP bearer token:

```sh
kubectl --namespace arangodb-mcp create secret generic arangodb-mcp \
  --from-literal=arango-root-password='<database-password>' \
  --from-literal=mcp-auth-token='<independent-random-token>'

helm upgrade --install arangodb-mcp deploy/helm/arangodb-mcp \
  --namespace arangodb-mcp --create-namespace \
  --set secrets.existingSecret=arangodb-mcp \
  --set arango.hosts=https://arangodb.example:8529 \
  --set image.digest=sha256:<published-image-digest>
```

Do not reuse the ArangoDB password as the MCP token. Avoid command-line `--set` for secret
values because shell history and Helm release history retain them.

## OIDC mode

OIDC is preferred for shared production services. The referenced Secret needs
`arango-root-password` for startup/readiness and `mcp-arango-credentials-json` for the
trusted actor mapping. Passwords in that mapping should use `password_env`; expose each
password from the same Secret with `secrets.extraEnv`.

```yaml
auth:
  mode: oidc
  oidc:
    issuer: https://id.example.com
    audience: arangodb-mcp
    resourceUrl: https://mcp.example.com/mcp
secrets:
  existingSecret: arangodb-mcp
  extraEnv:
    - name: ARANGO_ALICE_PASSWORD
      key: arango-alice-password
server:
  allowedHosts: mcp.example.com,arangodb-mcp:*,arangodb-mcp.arangodb-mcp.svc:*
```

The `mcp-arango-credentials-json` key could contain:

```json
{"alice":{"username":"alice_mcp","password_env":"ARANGO_ALICE_PASSWORD","databases":["tenant_a"]}}
```

The chart rejects incomplete OIDC values through `values.schema.json`. Insecure HTTP OIDC
is disabled by default and should only be enabled in disposable private test networks.

## Opt-in chart-created Secret

For a disposable development namespace, `secrets.create.enabled=true` accepts values below
`secrets.create`. This is explicitly not recommended for production: values are stored in
Helm release history. The generated Secret has `helm.sh/resource-policy: keep`, so uninstall
does not silently delete credentials; remove it manually after the environment is gone.

## Policy and observability

`policy` maps directly to the server's profile, toolset/denylist, result-contract, AQL,
confirmation, and concurrency controls. The default is the `readonly` profile with
JavaScript transactions and query-text logging disabled.

Prometheus metrics are enabled at `/metrics`. Enable `observability.serviceMonitor.enabled`
only when the Prometheus Operator CRDs are installed. Tracing defaults to disabled; OTLP
headers can be sourced from the existing Secret by enabling
`observability.tracing.headersSecretEnabled`.

## Hardening and scheduling

The defaults run as a non-root UID/GID, use a read-only root filesystem, deny privilege
escalation, drop all Linux capabilities, use RuntimeDefault seccomp, and do not mount a
service-account token. `/tmp` is the only writable `emptyDir`.

Set resource requests/limits for the workload. `affinity`, `nodeSelector`, `tolerations`,
`topologySpreadConstraints`, and an optional PodDisruptionBudget are available. Use at least
two replicas before enabling a PDB with `minAvailable: 1`.

Ingress is opt-in. Set TLS and `server.allowedHosts` to the public hostname when exposing the
service. `/livez` checks process liveness; `/readyz` verifies ArangoDB connectivity.

## Upgrade and rollback

1. Read the repository changelog and deprecation policy.
2. Pin `image.digest` to the reviewed release digest.
3. Render and validate first:
   `helm template arangodb-mcp deploy/helm/arangodb-mcp -f production.yaml`.
4. Run `helm upgrade --install ... --atomic --timeout 5m`.
5. Verify rollout, `/livez`, `/readyz`, and an authenticated MCP initialize/tool request.

External Secret updates do not change the Deployment template. After rotating a referenced
Secret, run:

```sh
kubectl rollout restart deployment/arangodb-mcp --namespace arangodb-mcp
kubectl rollout status deployment/arangodb-mcp --namespace arangodb-mcp
```

Use `helm rollback arangodb-mcp <revision>` for application rollback. Database schema/data
rollback is outside this chart; back up ArangoDB before any application change that modifies
data. Keep Secret key names stable across upgrades, or update the `secrets.keys` mapping in
the same atomic upgrade.
