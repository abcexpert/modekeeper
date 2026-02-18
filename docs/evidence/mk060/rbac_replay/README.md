# RBAC replay (MK-055)

This replay reproduces the real-cluster RBAC patch denial for `mk k8s verify`.

One command:

```bash
./docs/evidence/mk060/rbac_replay/setup.sh
```

Cleanup:

```bash
./docs/evidence/mk060/rbac_replay/cleanup.sh
```

Expected outcome:
- `report/mk060_rbac_replay/k8s_verify_latest.json` has `verify_blocker.kind=rbac_denied`
- `diagnostics.auth_can_i_get_deployments_by_namespace.mk055-rbac-deny=true`
- `diagnostics.auth_can_i_patch_deployments_by_namespace.mk055-rbac-deny=false`
