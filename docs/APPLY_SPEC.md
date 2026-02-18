# ModeKeeper — спецификация mk k8s apply (paid)

> Цель: описать планируемую команду автоматического применения изменений в Kubernetes.
> Это спецификация поведения и артефактов; реализация может появиться позже.

## Цель
- Безопасно и воспроизводимо применять план изменений, сформированный в режиме plan-only.
- Сохранять полную трассировку действий (audit) и причину блокировок.

## Ограничения и безопасность
- Применение доступно только в платном режиме (лицензия/капабилити).
- По умолчанию применяется только план, успешно прошедший verify (verify-ok).
- Никаких изменений без явного разрешения в виде лицензии и verify-ok.
- Опциональный `--force` допускается только под явным подтверждением оператора.

## CLI
```
mk k8s apply --plan PATH --out OUT [--force]
```
- `--plan` обязателен и соответствует формату `k8s_plan.json`.
- `--out` обязателен, путь для отчётов и explain-log.
- `--force` — только под явным подтверждением; позволяет обойти gate verify-ok.

## Gate (лицензия + verify)
- Apply разрешён только при активной лицензии/капабилити.
- Apply выполняется только если:
  - есть отчёт verify для данного плана, и
  - `verify.ok == true`.
- Иначе — блокировка с отчётом `ok=false`.
- `--force` допускает apply при `verify.ok != true`, но не отменяет требования лицензии.

## Explain events
- `k8s_apply_start`
- `k8s_apply_blocked`
- `k8s_apply_applied`
- `k8s_apply_report`
- `k8s_apply_error`

## Артефакты
- `k8s_apply_*.json` — полный отчёт применения.
- `k8s_apply_latest.json` — копия последнего отчёта.

Содержимое отчёта:
- `k8s_plan_path`
- `k8s_plan_items`
- `verify_report_path` (если найден)
- `license_ok` (bool)
- `verify_ok` (bool или null, если отчёт не найден)
- `force` (bool)
- `kubectl_context` (строка или null)
- `checks`:
  - `kubectl_present` (bool)
  - `verify_report_found` (bool)
- `actions[]` — per-item результат применения:
  - `namespace`, `name`
  - `patch_attempted` (bool)
  - `ok` (bool)
  - `rc` (int)
  - `stdout` (truncated)
  - `stderr` (truncated)
- `ok` — true только если все items применены без ошибок.

## Семантика ошибок
- Ошибка чтения/парсинга/валидации плана: `rc=2`, **без артефактов** (только explain.jsonl).
- Блокировка (лицензия/verify-ok/guardrails): `rc=2`, отчёт с `ok=false`.
- Ошибки kubectl: отчёт с `ok=false` и детальными per-item данными.

## Audit
- Для каждого kubectl-вызова записывать `argv`, `rc`, `stdout`, `stderr`.
- Ограничение размера stdout/stderr: хранить только первые N байт (значение определяется в реализации).

## Рекомендованный workflow
1) `mk k8s render` → получить скрипт и отчёт.
2) `mk k8s verify` → убедиться, что `verify.ok == true`.
3) `mk k8s apply` → применить (только при лицензии).

Если отчёт verify отсутствует или не найден — apply **не выполняется**; возвращается блокировка с `ok=false` и рекомендацией запустить verify.
