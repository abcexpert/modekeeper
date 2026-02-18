"""Best-effort parsing for Kubernetes RBAC forbidden errors."""

from __future__ import annotations

import re


_FORBIDDEN_PATTERN = re.compile(
    r'User\s+"(?P<user>[^"]+)"\s+cannot\s+(?P<verb>[a-z]+)\s+resource\s+"(?P<resource>[^"]+)"\s+'
    r'in\s+API\s+group\s+"(?P<api_group>[^"]*)"\s+'
    r'(?:(?:in\s+the\s+namespace\s+"(?P<namespace>[^"]+)")|(?:at\s+the\s+cluster\s+scope))',
    re.IGNORECASE,
)

_NAME_PATTERN = re.compile(r'"(?P<name>[^"]+)"\s+is forbidden:', re.IGNORECASE)


def _build_hint(
    *,
    user: str,
    verb: str,
    resource: str,
    api_group: str,
    namespace: str | None,
    scope: str,
    name: str | None,
) -> str:
    api_groups = [api_group]
    if scope == "namespaced":
        rule_ref = f'Role in namespace "{namespace}"'
        binding = "RoleBinding"
    else:
        rule_ref = "ClusterRole"
        binding = "ClusterRoleBinding"
    rule = f"apiGroups={api_groups}, resources={[resource]}, verbs={[verb]}"
    scoped_name = f' Optionally add resourceNames=["{name}"] for least privilege.' if name else ""
    return (
        f'Grant a {rule_ref} rule with {rule}; then bind it to user "{user}" using {binding}.{scoped_name}'
    )


def parse_k8s_forbidden(text: str) -> dict | None:
    """Parse common kubectl Forbidden errors into structured RBAC diagnostics."""
    if not isinstance(text, str):
        return None
    raw = text.strip()
    if not raw:
        return None
    lower = raw.lower()
    if "forbidden" not in lower or "cannot" not in lower:
        return None

    match = _FORBIDDEN_PATTERN.search(raw)
    if not match:
        return None

    user = match.group("user")
    verb = match.group("verb").lower()
    resource = match.group("resource")
    api_group = match.group("api_group")
    namespace = match.group("namespace")
    scope = "namespaced" if namespace else "cluster"

    name_match = _NAME_PATTERN.search(raw)
    name = name_match.group("name") if name_match else None

    suggested_rule = {
        "apiGroups": [api_group],
        "resources": [resource],
        "verbs": [verb],
    }
    hint = _build_hint(
        user=user,
        verb=verb,
        resource=resource,
        api_group=api_group,
        namespace=namespace,
        scope=scope,
        name=name,
    )

    return {
        "user": user,
        "verb": verb,
        "resource": resource,
        "api_group": api_group,
        "namespace": namespace,
        "name": name,
        "scope": scope,
        "suggested_rule": suggested_rule,
        "hint": hint,
    }

