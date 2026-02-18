from __future__ import annotations


def build_k8s_plan(
    proposed_actions: list[object],
    *,
    namespace: str,
    deployment: str,
) -> list[dict]:
    items_by_target: dict[tuple[str, str], dict] = {}
    for action in proposed_actions:
        knob = getattr(action, "knob", None)
        target = getattr(action, "target", None)
        key = (namespace, deployment)
        item = items_by_target.get(key)
        if item is None:
            item = {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "namespace": namespace,
                "name": deployment,
                "reason": "coalesced",
                "patch": {
                    "metadata": {"annotations": {}},
                    "spec": {"template": {"metadata": {"annotations": {}}}},
                },
            }
            items_by_target[key] = item

        annotation_key = f"modekeeper/knob.{knob}"
        item["patch"]["metadata"]["annotations"][annotation_key] = f"{target}"
        item["patch"]["spec"]["template"]["metadata"]["annotations"][annotation_key] = f"{target}"
    return list(items_by_target.values())
