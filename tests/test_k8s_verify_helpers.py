from modekeeper.cli import _classify_k8s_verify_dry_run_failure, _parse_auth_can_i_answer


def test_classify_k8s_verify_dry_run_failure_forbidden_and_not_found() -> None:
    assert (
        _classify_k8s_verify_dry_run_failure(
            'Error from server (Forbidden): deployments.apps "dep1" is forbidden: User "system:serviceaccount:ns1:sa" cannot patch resource "deployments"'
        )
        == "rbac_denied"
    )
    assert (
        _classify_k8s_verify_dry_run_failure(
            'Error from server (NotFound): deployments.apps "dep1" not found'
        )
        == "deployment_missing"
    )
    assert (
        _classify_k8s_verify_dry_run_failure('Error from server (NotFound): namespaces "ns1" not found')
        == "namespace_missing"
    )


def test_parse_auth_can_i_answer() -> None:
    assert _parse_auth_can_i_answer("yes\n") is True
    assert _parse_auth_can_i_answer("no") is False
    assert _parse_auth_can_i_answer("maybe") is None
    assert _parse_auth_can_i_answer("") is None


def test_parse_auth_can_i_answer_json_status_allowed_false() -> None:
    assert _parse_auth_can_i_answer('{"status":{"allowed":false}}') is False


def test_parse_auth_can_i_answer_multiline_last_non_empty_line() -> None:
    assert _parse_auth_can_i_answer("warning...\nno\n") is False
