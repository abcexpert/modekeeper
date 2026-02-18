# Passports v0

`passport.v0` - это контракт для безопасного управления аккордами и актуаторами в конкретном окружении.
Он не запускает apply сам по себе и не интегрирован в `closed-loop/watch` по умолчанию.

## Что описывает passport.v0
- `schema_version`: всегда `passport.v0`.
- `name`: имя профиля/шаблона.
- `allowed_chords`: разрешённые canonical chord IDs.
- `allowed_actuators.hot`: ручки для потенциально "горячих" изменений (runtime-capable).
- `allowed_actuators.cold`: ручки для "холодных" изменений (обычно через rollout).
- `limits`: численные лимиты (обязательно `cooldown_s`, `max_delta_per_step`, `relock_stable_intervals`; опционально `knob_limits`).
- `invariants`: список инвариантов, которые нельзя нарушать.
- `cooldowns`: доп. cooldown-политики по фазам/сценариям.
- `gates`: gate-правила (например `apply=false`, `require_verify_ok=true`).

Canonical chord IDs для `passport.v0`:
- `NORMAL-HOLD`
- `DRIFT-RETUNE`
- `BURST-ABSORB`
- `INPUT-STRAGGLER`
- `RECOVER`
- `RELOCK`

## Hot vs Cold
- `hot`: допускаются только там, где платформа реально поддерживает runtime-изменение.
- `cold`: изменения через безопасный deployment/rollout-поток.

## Limits, invariants, cooldowns, gates
- `limits` ограничивают скорость и амплитуду изменения.
- `invariants` фиксируют то, что нельзя ломать (например стабильность global batch).
- `cooldowns` снижают дребезг и предотвращают oscillations.
- `gates` определяют условия допуска действий; в шаблонах v0 по умолчанию `apply=false`.

## Каталог шаблонов
Встроенные шаблоны:
- `pilot`
- `safe`
- `perf`
- `cost`
- `io`
- `comm`
- `recovery`

## CLI onboarding
Список шаблонов:
```bash
mk passport templates
```

Показать шаблон:
```bash
mk passport show --template safe
```

Проверить файл паспорта:
```bash
mk passport validate --file ./passport.json
```

Поведение `validate`:
- `rc=0`: файл валиден.
- `rc=2`: файл невалиден (ошибка печатается в `stderr`).

---

## Контекст (предыдущее описание)

## Паспорт как контракт заказа
Паспорт - это контракт между клиентом и автотюнингом ModeKeeper. Он задаёт рамки допустимых аккордов, актуаторов, риска и инвариантов, чтобы автотюнинг оставался безопасным и переносимым между окружениями.

Смысл паспорта: одна и та же логика аккордов не должна без ограничений переноситься между разными кластерами, моделями и SLO. Паспорт фиксирует, что именно разрешено делать в конкретном контексте и что допускается только как `propose-only`.

## Что внутри паспорта (обязательные поля)
- `id`, `version`, `owner`: идентификатор, версия и ответственный.
- `allowed_chords`: разрешённые аккорды (safe и, при наличии телеметрии, advanced).
- `allowed_actuators`: список ручек и режимов `hot/cold`.
- `hot/cold semantics`: в k8s-подходе честно считаем, что фактический `apply` обычно идёт через rollout, то есть по сути `cold`; "hot" означает только допустимость планирования/проверки или runtime-изменение там, где платформа действительно это поддерживает.
- `invariants`: обязательные инварианты (`global_batch`, границы SLO, допустимый риск деградации).
- `limits`: `min/max`, `max delta` за шаг, `cooldown`, `freeze window`.
- `safety_gates`: `verify-ok`, `kill-switch`, policy для paid/apply.
- `observability_requirements`: без каких метрик конкретный аккорд не активируем.

## Когда паспорт меняется
Паспорт пересматривается при изменении базовых условий:
- смена железа, сети или топологии кластера;
- смена модели, датасета или профиля нагрузки;
- изменение SLO или риск-профиля заказчика.

Принцип обновления простой:
- сначала `observe-only`;
- потом калибровка лимитов и телеметрии;
- затем ограниченный `verify/apply` в рамках нового паспорта.

## Пример A: production, консервативный
- Позиция: минимальный риск, предсказуемость важнее скорости.
- Аккорды `on`: `NORMAL-HOLD`, `DRIFT-RETUNE`, `BURST-ABSORB`, `INPUT-STRAGGLER`, `RECOVER + RELOCK`.
- Аккорды `off`: `COMM-CONGESTION`, `NEAR-HANG/TIMEOUT-GUARD`.
- Actuators allowed: `grad_accum_steps`, `microbatch_size`, `dataloader_prefetch_factor`, `concurrency`.
- Actuators propose-only: `timeout_ms`, `dataloader_num_workers`, `comm_bucket_mb`.
- Запрещено: placement/reschedule, tempo/pacing, timeout/retry policy apply без явного разрешения.
- Инварианты: `global_batch` в узком коридоре, SLO по `p95/p99 step-time`, ограничение на rollback-risk.
- `verify-only` vs `apply`: по умолчанию `verify-only`; `apply` максимально ограничен и только после `verify-ok` + paid gate + kill-switch check.
- Параметры риска: маленький `alpha`, строгие `cooldown` и `max delta`.

## Пример B: R&D, speed
- Позиция: приоритет скорости итераций, риск выше, но контролируемый.
- Аккорды `on`: все safe + `COMM-CONGESTION` при подтверждённой comm-телеметрии.
- Аккорды `off`: `NEAR-HANG/TIMEOUT-GUARD` до появления watchdog-сигналов нужного качества.
- Actuators allowed: safe-ручки + `comm_bucket_mb` на boundary и только при observability-gates.
- Actuators propose-only: `timeout_ms` по умолчанию, если нет отдельного разрешения.
- Инварианты: `global_batch` сохраняется, SLO допускает более широкий рабочий коридор для `p95/p99 step-time`.
- `verify-only` vs `apply`: `verify` обязателен всегда; `apply` разрешён на ограниченных шагах и после калибровки.
- Параметры риска: `alpha` больше в рамках лимитов, `cooldown` короче, но `max delta` и kill-switch обязательны.

## Каталог паспортов v0
### pilot
- Цель: безопасный старт и сбор базовой телеметрии.
- Allowed chords: нет auto-активации, только propose.
- Запрещённые актуаторы: все apply-актуаторы.
- Apply policy: только `observe + plan + verify`, `apply` запрещён.

### safe
- Цель: минимальный риск для production.
- Allowed chords: safe chords v1.
- Запрещённые актуаторы: placement/reschedule, tempo/pacing, timeout/retry apply.
- Apply policy: в основном `verify-only`; apply только по явному разрешению и после калибровки.

### perf
- Цель: максимум производительности в контролируемых границах.
- Allowed chords: safe chords v1, advanced по gate (при телеметрии).
- Запрещённые актуаторы: изменения без observability-gates.
- Apply policy: разрешён при `verify-ok`, paid-gate и лимитах по шагу.

### cost
- Цель: снизить стоимость без срыва SLO.
- Allowed chords: safe chords v1 с фокусом на `DRIFT-RETUNE` и `BURST-ABSORB`.
- Запрещённые актуаторы: timeout/retry apply, placement/reschedule.
- Apply policy: консервативный apply после стабильной калибровки.

### io
- Цель: стабилизировать input-путь и убрать страгглеры.
- Allowed chords: safe chords v1, приоритет `INPUT-STRAGGLER`.
- Запрещённые актуаторы: агрессивные изменения concurrency/workers вне лимитов.
- Apply policy: частичный apply, `timeout_ms` по умолчанию propose-only.

### recovery
- Цель: восстановление после инцидентов с минимальным риском рецидива.
- Allowed chords: safe chords v1, при необходимости `RECOVER + RELOCK` как основной.
- Запрещённые актуаторы: любые резкие изменения, нарушающие freeze/cooldown.
- Apply policy: поэтапный apply с обязательным `verify-ok` и жёстким kill-switch.

### comm (опционально)
- Цель: снять коммуникационные узкие места в DDP.
- Allowed chords: safe chords + `COMM-CONGESTION` только при качественной comm-телеметрии.
- Запрещённые актуаторы: `comm_bucket_mb` без allreduce/comm-latency сигналов.
- Apply policy: ограниченный apply на boundary, fallback в propose-only при потере телеметрии.

## Связанные документы
- `docs/CUSTOM_PASSPORTS.md`
- `docs/CHORDS.md`
- `docs/product.md`
- `docs/SNAPSHOT.md`
