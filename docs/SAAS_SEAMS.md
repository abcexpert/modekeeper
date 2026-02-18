# SaaS Seams: offline-first bundle + manifest

## Зачем нужны seams
Для SaaS-перехода важен чистый контракт между:
- локальным read-only execution (у клиента);
- будущим control-plane (у нас).

`mk export bundle` фиксирует этот seam:
- локально собираются артефакты (`preflight/eval/watch/roi` + summary/explain);
- формируется детерминированный `bundle_manifest.json`;
- создаётся переносимый `bundle.tar.gz` без доступа к кластеру и без мутаций.

Плюсы:
- customer-safe: только чтение артефактов;
- offline-first: можно передать bundle вручную;
- auditable: file-level digests + run_id + schema versioning.

## Что входит в bundle.v0
- `schema_version`: `bundle.v0`
- `created_at`, `tool_version`, `run_id`
- `inputs_root`
- `metering`:
  - `sample_count`
  - `watch.duration_s/iterations_done/proposed_total/blocked_total/applied_total`
  - `roi.opportunity_hours_est/proposed_actions_count/ok/top_blocker`
- `environment` (prefer `eval.environment`, fallback из watch last iteration)
- `files[]`:
  - `rel_path`, `sha256`, `size_bytes`, `schema_version`, `kind`
- `notes` (missing inputs и best-effort предупреждения)

## Offline-first workflow
1. Запустить read-only pipeline (`preflight`, `eval`, `watch --dry-run`, `roi report`).
2. Выполнить `mk export bundle --in report --out report/bundle`.
3. Передать `bundle.tar.gz` + `bundle_summary.md`.
4. На стороне получателя проверять manifest/digests до любого импорта.

Это даёт минимальный SaaS seam уже сейчас, без control-plane зависимости.

## Future control-plane API (sketch)
`POST /v1/bundles`
- body: `multipart/form-data`
  - `manifest`: `bundle_manifest.json`
  - `bundle`: `bundle.tar.gz`
- response:
  - `bundle_id`
  - `ingest_status` (`accepted` | `rejected`)
  - `reasons[]`

Проверки ingestion:
- schema/version compatibility;
- digest validation (`files[].sha256`);
- metering extraction в billing pipeline.

## Auth / licensing / metering mapping
- AuthN/AuthZ:
  - tenant token + scoped project permissions (`bundle:write`, `bundle:read`).
- Licensing:
  - free/pilot/paid entitlements привязываются к tenant/project при ingest.
- Metering:
  - `sample_count`, `watch.*`, `roi.*` переходят в usage accounting;
  - `top_blocker` и `notes` идут в CS/solutioning аналитики.

Итог: `export bundle` задаёт стабильный, проверяемый контракт между локальным контуром и будущим SaaS control-plane.
