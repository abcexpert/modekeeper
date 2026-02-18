from modekeeper.k8s.rbac_diagnostics import parse_k8s_forbidden


def test_parse_k8s_forbidden_namespaced_patch_error() -> None:
    text = (
        'Error from server (Forbidden): deployments.apps "dep1" is forbidden: '
        'User "system:serviceaccount:ns1:sa" cannot patch resource "deployments" '
        'in API group "apps" in the namespace "ns1"'
    )
    parsed = parse_k8s_forbidden(text)
    assert parsed is not None
    assert parsed["user"] == "system:serviceaccount:ns1:sa"
    assert parsed["verb"] == "patch"
    assert parsed["resource"] == "deployments"
    assert parsed["api_group"] == "apps"
    assert parsed["namespace"] == "ns1"
    assert parsed["name"] == "dep1"
    assert parsed["scope"] == "namespaced"
    assert parsed["suggested_rule"] == {
        "apiGroups": ["apps"],
        "resources": ["deployments"],
        "verbs": ["patch"],
    }
    assert "Role" in parsed["hint"]
    assert "RoleBinding" in parsed["hint"]


def test_parse_k8s_forbidden_cluster_scope_list_error() -> None:
    text = (
        'Error from server (Forbidden): nodes is forbidden: '
        'User "alice@example.com" cannot list resource "nodes" in API group "" '
        "at the cluster scope"
    )
    parsed = parse_k8s_forbidden(text)
    assert parsed is not None
    assert parsed["user"] == "alice@example.com"
    assert parsed["verb"] == "list"
    assert parsed["resource"] == "nodes"
    assert parsed["api_group"] == ""
    assert parsed["namespace"] is None
    assert parsed["name"] is None
    assert parsed["scope"] == "cluster"
    assert parsed["suggested_rule"] == {
        "apiGroups": [""],
        "resources": ["nodes"],
        "verbs": ["list"],
    }
    assert "ClusterRole" in parsed["hint"]
    assert "ClusterRoleBinding" in parsed["hint"]


def test_parse_k8s_forbidden_returns_none_for_unrecognized_text() -> None:
    assert parse_k8s_forbidden("random kubectl failure that is not an rbac denial") is None

