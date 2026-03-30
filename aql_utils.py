import re

_AQL_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_\-:.]*$")


def validate_aql_identifier(name: str, label: str = "identifier") -> str:
    """Validate and return an AQL-safe identifier.

    Raises ValueError if the identifier contains characters that could
    alter AQL query semantics when used in backtick-quoted positions.
    """
    if not name:
        raise ValueError(f"{label} cannot be empty.")
    if not _AQL_IDENTIFIER_RE.match(name):
        raise ValueError(
            f"Unsafe {label} '{name}': must start with a letter or underscore "
            "and contain only letters, digits, underscores, hyphens, colons, or dots."
        )
    return name


def validate_aql_identifiers(names: list[str], label: str = "identifier") -> list[str]:
    """Validate a list of AQL identifiers."""
    return [validate_aql_identifier(n, label) for n in names]
