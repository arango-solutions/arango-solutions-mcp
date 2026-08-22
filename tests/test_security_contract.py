"""Static contracts for the repository security controls."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_security_workflow_preserves_codeql_and_dependency_audit():
    workflow = _read(".github/workflows/security.yml")
    release = _read(".github/workflows/release.yml")

    assert "github/codeql-action/init@v3" in workflow
    assert "github/codeql-action/analyze@v3" in workflow
    assert "poetry run python -m pip_audit" in workflow
    assert "--ignore-vuln" not in workflow
    assert 'tags:\n      - "v*.*.*"' in release
    assert "pypa/gh-action-pypi-publish@release/v1" in release
    assert "id-token: write" in release
    assert "actions/attest-build-provenance@v2" in release
    assert "actions/attest-sbom@v2" in release
    assert "cosign sign --yes" in release
    assert "cosign verify" in release
    assert "image-ref: ${{ env.IMAGE }}@${{ steps.build.outputs.digest }}" in release
    assert "gh attestation verify dist/*.whl" in release
    assert 'gh release create "$GITHUB_REF_NAME"' in release
    assert "python-sbom.spdx.json" in release
    assert "container-sbom.spdx.json" in release


def test_security_workflow_scans_full_git_history_for_secrets():
    workflow = _read(".github/workflows/security.yml")
    config = _read(".gitleaks.toml")

    assert "secret-scan:" in workflow
    assert "fetch-depth: 0" in workflow
    assert "ghcr.io/gitleaks/gitleaks:v8.30.1" in workflow
    assert "git --redact --verbose" in workflow
    assert "--config /repo/.gitleaks.toml" in workflow
    assert "[extend]" in config
    assert "useDefault = true" in config


def test_security_workflow_builds_then_scans_the_application_image():
    workflow = _read(".github/workflows/security.yml")
    ignore = _read(".trivyignore.yaml")
    build = "docker build --provenance=false --tag arango-solutions-mcp:security-scan ."
    scan = "uses: aquasecurity/trivy-action@v0.36.0"

    assert "container-vulnerability-scan:" in workflow
    assert workflow.index(build) < workflow.index(scan)
    assert "image-ref: arango-solutions-mcp:security-scan" in workflow
    assert "scanners: vuln" in workflow
    assert "vuln-type: os,library" in workflow
    assert "severity: HIGH,CRITICAL" in workflow
    assert "ignore-unfixed: false" in workflow
    assert 'exit-code: "1"' in workflow
    assert "trivyignores: .trivyignore.yaml" in workflow
    for advisory in ("GHSA-6v7p-g79w-8964", "CVE-2025-47273"):
        assert f"id: {advisory}" in ignore
    assert ignore.count("expired_at: 2026-08-20") == 2
    assert "GitHub issue #5" in ignore
    assert ignore.count("final runtime filesystem") == 2


def test_security_policy_defines_remediation_and_exception_contract():
    policy = _read("SECURITY.md")

    for severity, deadline in (
        ("Critical", "7 calendar days"),
        ("High", "30 calendar days"),
        ("Medium", "90 calendar days"),
        ("Low", "180 calendar days"),
    ):
        assert severity in policy
        assert deadline in policy

    assert "New unexcepted High or Critical" in policy
    assert "block merge" in policy
    for required_exception_field in (
        "advisory or scanner rule identifier",
        "tracking issue",
        "accountable owner",
        "compensating controls",
        "explicit expiration date",
    ):
        assert required_exception_field in policy

    assert "Real credentials cannot be excepted." in policy
    assert "There are no active dependency-audit exceptions." in policy
