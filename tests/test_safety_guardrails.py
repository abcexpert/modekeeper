import json
from pathlib import Path

from modekeeper.cli import _run_closed_loop_once, build_parser
from modekeeper.knobs import ActuatorRegistry, Knob
from modekeeper.policy.actions import Action
from modekeeper.safety.explain import ExplainLog
from modekeeper.safety.guards import Guardrails


def _registry():
    r = ActuatorRegistry()
    r.register(Knob("dataloader_num_workers", 1, 16, step=1, value=4))
    return r


def test_allowlist_blocks_unknown_knob(tmp_path: Path):
    r = _registry()
    explain = ExplainLog(tmp_path / "explain.jsonl")
    g = Guardrails(registry=r, explain=explain)

    res = g.evaluate_and_apply([Action("no_such_knob", 1, "test")], apply_changes=True)
    assert res[0].blocked is True
    assert res[0].reason == "unknown_knob"


def test_kill_switch_env_blocks_apply(monkeypatch, tmp_path: Path):
    r = _registry()
    explain = ExplainLog(tmp_path / "explain.jsonl")
    g = Guardrails(registry=r, explain=explain)

    monkeypatch.setenv("MODEKEEPER_KILL_SWITCH", "1")
    res = g.evaluate_and_apply([Action("dataloader_num_workers", 2, "test")], apply_changes=True)
    assert res[0].blocked is True
    assert res[0].reason == "kill_switch"
    assert res[0].dry_run is True


def test_entitlement_missing_blocks_apply_at_mutation_layer(tmp_path: Path):
    r = _registry()
    explain = ExplainLog(tmp_path / "explain.jsonl")
    g = Guardrails(registry=r, explain=explain)

    res = g.evaluate_and_apply(
        [Action("dataloader_num_workers", 2, "test")],
        apply_changes=True,
        entitlement_apply_enabled=False,
    )
    assert res[0].blocked is True
    assert res[0].reason == "entitlement_missing"
    assert res[0].dry_run is True
    assert r.get("dataloader_num_workers").value == 4


def test_rate_limit_blocks_second_apply(tmp_path: Path):
    r = _registry()
    explain = ExplainLog(tmp_path / "explain.jsonl")
    g = Guardrails(registry=r, explain=explain, min_interval_s=3600)

    a = Action("dataloader_num_workers", 2, "test")

    res1 = g.evaluate_and_apply([a], apply_changes=True)
    assert res1[0].applied is True
    assert r.get("dataloader_num_workers").value == 2

    res2 = g.evaluate_and_apply([Action("dataloader_num_workers", 3, "test")], apply_changes=True)
    assert res2[0].blocked is True
    assert res2[0].reason == "cooldown_active"
    assert r.get("dataloader_num_workers").value == 2

    records = [
        json.loads(line)
        for line in (tmp_path / "explain.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    blocked = [rec for rec in records if rec.get("event") == "blocked"]
    assert blocked
    assert blocked[-1].get("payload", {}).get("reason") == "cooldown_active"


def test_apply_gate_dry_run_does_not_change_registry(tmp_path: Path):
    r = _registry()
    explain = ExplainLog(tmp_path / "explain.jsonl")
    g = Guardrails(registry=r, explain=explain)

    before = r.get("dataloader_num_workers").value
    res = g.evaluate_and_apply(
        [Action("dataloader_num_workers", before + 1, "test")],
        apply_changes=False,
    )
    assert res[0].blocked is False
    assert res[0].reason == "dry_run"
    assert res[0].dry_run is True
    assert r.get("dataloader_num_workers").value == before


def test_max_delta_blocks_second_apply_and_writes_explain(tmp_path: Path):
    r = _registry()
    explain = ExplainLog(tmp_path / "explain.jsonl")
    g = Guardrails(registry=r, explain=explain, min_interval_s=0, max_delta_per_step=1)

    res1 = g.evaluate_and_apply([Action("dataloader_num_workers", 5, "test")], apply_changes=True)
    assert res1[0].applied is True
    assert r.get("dataloader_num_workers").value == 5

    res2 = g.evaluate_and_apply([Action("dataloader_num_workers", 7, "test")], apply_changes=True)
    assert res2[0].blocked is True
    assert res2[0].reason == "max_delta_exceeded"
    assert r.get("dataloader_num_workers").value == 5

    records = [
        json.loads(line)
        for line in (tmp_path / "explain.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    blocked = [rec for rec in records if rec.get("event") == "blocked"]
    assert blocked
    payload = blocked[-1].get("payload", {})
    assert payload.get("reason") == "max_delta_exceeded"
    assert payload.get("max_delta_per_step") == 1


def test_rollback_to_last_stable_restores_and_logs_explain(tmp_path: Path):
    r = _registry()
    explain = ExplainLog(tmp_path / "explain.jsonl")
    g = Guardrails(registry=r, explain=explain, min_interval_s=3600, max_delta_per_step=1)

    knob = r.get("dataloader_num_workers")
    assert knob is not None
    knob.apply(2)
    g.mark_stable_profile()

    knob.apply(5)
    assert knob.value == 5

    res = g.rollback_to_last_stable(reason="incident_worsened", apply_changes=True)
    assert res
    assert all(item.reason == "rollback" for item in res)
    assert knob.value == 2

    records = [
        json.loads(line)
        for line in (tmp_path / "explain.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rollback = [rec for rec in records if rec.get("event") == "rollback"]
    assert rollback
    payload = rollback[-1].get("payload", {})
    assert payload.get("reason") == "incident_worsened"
    assert payload.get("before", {}).get("dataloader_num_workers") == 5
    assert payload.get("after", {}).get("dataloader_num_workers") == 2
    assert "dataloader_num_workers" in payload.get("changed", [])


def test_cli_cooldown_s_is_propagated_to_guardrails(tmp_path: Path):
    parser = build_parser()
    args = parser.parse_args(
        [
            "closed-loop",
            "run",
            "--dry-run",
            "--scenario",
            "drift",
            "--out",
            str(tmp_path),
            "--cooldown-s",
            "123",
        ]
    )
    report, _ = _run_closed_loop_once(
        scenario=args.scenario,
        k8s_namespace=args.k8s_namespace,
        k8s_deployment=args.k8s_deployment,
        out_dir=Path(args.out),
        apply_requested=bool(args.apply),
        observe_source=args.observe_source,
        observe_path=Path(args.observe_path) if args.observe_path else None,
        observe_record_raw_path=Path(args.observe_record_raw) if args.observe_record_raw else None,
        observe_record_raw_mode="w",
        observe_duration_ms=1000,
        observe_container=args.observe_container,
        license_path=None,
        policy=args.policy,
        cooldown_s=int(args.cooldown_s),
    )
    assert report.get("safety_cooldown_s") == 123


def test_cli_max_delta_per_step_is_propagated_to_report(tmp_path: Path):
    parser = build_parser()
    args = parser.parse_args(
        [
            "closed-loop",
            "run",
            "--dry-run",
            "--scenario",
            "drift",
            "--out",
            str(tmp_path),
            "--max-delta-per-step",
            "123",
        ]
    )
    report, _ = _run_closed_loop_once(
        scenario=args.scenario,
        k8s_namespace=args.k8s_namespace,
        k8s_deployment=args.k8s_deployment,
        out_dir=Path(args.out),
        apply_requested=bool(args.apply),
        observe_source=args.observe_source,
        observe_path=Path(args.observe_path) if args.observe_path else None,
        observe_record_raw_path=Path(args.observe_record_raw) if args.observe_record_raw else None,
        observe_record_raw_mode="w",
        observe_duration_ms=1000,
        observe_container=args.observe_container,
        license_path=None,
        policy=args.policy,
        cooldown_s=int(args.cooldown_s),
        max_delta_per_step=int(args.max_delta_per_step),
    )
    assert report.get("safety_max_delta_per_step") == 123
