# Handoff: canonical

## Точка продолжения
- Ветка: `main`
- HEAD: `9e2faa53f922f8f1ff438fab4009109d395640d2`
- Последний коммит: `docs: add chat handoff guide (mk handover)`

## Где продолжать чтение
1. `docs/HANDOFF_CHAT.md`
2. `docs/SNAPSHOT.md`
3. `docs/TICKETS.md`
4. `docs/QUICKSTART.md`
5. `docs/SAAS_SEAMS.md`

## Рабочие пути
- Локально (WSL): `~/code/modekeeper`
- Venv: `~/code/modekeeper/.venv`
- `abc2` bare repo: `/home/oleg/modekeeper-remote.git`
- `abc2` working copy: `/root/modekeeper`
- `abc2` backups: `/root/backups/modekeeper`

## Каноничный demo flow (CPU-only, kind)

```bash
docker build -f docker/trainer/Dockerfile -t modekeeper-trainer:dev .
```

```bash
kind load docker-image modekeeper-trainer:dev --name modekeeper
```

```bash
kubectl apply -f k8s/trainer-demo-cpu.yaml
```

```bash
mk eval k8s --k8s-namespace default --k8s-deployment trainer --observe-duration 60s --out report/eval_k8s
```

```bash
mk closed-loop watch --scenario drift --dry-run --observe-source k8s --k8s-namespace default --k8s-deployment trainer --observe-duration 60s --out report/watch_k8s --interval 10s --max-iterations 2
```

```bash
mk roi report --preflight report/preflight/preflight_latest.json --eval report/eval_k8s/eval_latest.json --watch report/watch_k8s/watch_latest.json --out report/roi
```

```bash
mk export bundle --in report --out report/bundle
```

## Bundle для передачи
- `report/bundle/bundle.tar.gz`
- `report/bundle/bundle_summary.md`
- `report/bundle/bundle_manifest.json`

## Backup (abc2, canonical)

```bash
set -euo pipefail

REMOTE_BARE="/home/oleg/modekeeper-remote.git"
BACKUP_DIR="/root/backups/modekeeper"
TS="$(date -u +%Y%m%d_%H%M%SZ)"
BUNDLE_PATH="$BACKUP_DIR/modekeeper_${TS}.bundle"
SHA_PATH="${BUNDLE_PATH}.sha256"

mkdir -p "$BACKUP_DIR"

git --git-dir="$REMOTE_BARE" rev-parse --short=12 HEAD

git --git-dir="$REMOTE_BARE" bundle create "$BUNDLE_PATH" --all
sha256sum "$BUNDLE_PATH" > "$SHA_PATH"

ln -sfn "$BUNDLE_PATH" "$BACKUP_DIR/latest.bundle"
cp "$SHA_PATH" "$BACKUP_DIR/latest.bundle.sha256"

sha256sum -c "$BACKUP_DIR/latest.bundle.sha256"
ls -la "$BACKUP_DIR"
```

## Приоритет следующих задач
1. Kill-switch absolute во всех путях apply.
2. License key management (`kid` + rotation process).
3. Bundle ingest verifier (manifest/schema/hash checks).
4. Commercial packaging (customer/investor deliverables + SKU).

## Сообщение для нового чата
```text
replace file content exactly with the canonical handoff from chat
```
