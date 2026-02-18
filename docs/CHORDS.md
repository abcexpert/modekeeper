# Аккорды в ModeKeeper

## Что такое аккордная подстройка
Аккордная подстройка в ModeKeeper - это тюнинг режима, а не одиночной ручки. Аккорд задаётся как вектор изменений `v` по нескольким взаимосвязанным knobs и интенсивность шага `alpha`, которая масштабирует этот вектор в рамках safety-лимитов.

В отличие от одиночного автотюнинга, где меняется один параметр и остальное "подтягивается" неявно, аккорд сразу учитывает связки между ручками. Это уменьшает риск случайной деградации, потому что изменения применяются как согласованный пакет, а не как набор независимых правок.

На практике аккорд используется в контуре `observe -> analyze_signals -> propose_actions -> plan/verify/apply gates`. По умолчанию ModeKeeper остаётся в безопасном режиме `plan-only + verify`: система предлагает и проверяет, но не применяет автоматически без явного разрешения.

## Инвариант и компенсация
Базовый инвариант для training-контура:
- `global_batch ~= microbatch_size * grad_accum_steps * world_size`

Правило компенсации:
- если `grad_accum_steps` увеличиваем, `microbatch_size` при необходимости снижаем, чтобы удержать `global_batch` в согласованном коридоре;
- если `microbatch_size` уменьшаем для tail-latency или памяти, `grad_accum_steps` поднимаем в допустимых пределах.

## Chord library v1 (Safe Auto)
В v1 auto-режим ограничен только "безопасными" аккордами ниже. Advanced аккорды выключены по умолчанию.

### NORMAL-HOLD
- Режим: штатная работа без подтверждённого инцидента, удержание текущего состояния.
- Сигналы детекта: нет устойчивого `drift`, нет `burst`, нет `straggler`, нет устойчивого `gpu_saturated`; метрики в пределах целевых коридоров (`p95/p99 step-time` стабильны, `straggler score` низкий, `GPU idle` без аномалий).
- Аккорд (вектор изменений): нулевой вектор; `grad_accum_steps`, `microbatch_size`, `dataloader_prefetch_factor`, `concurrency`, `dataloader_num_workers`, `timeout_ms`, `comm_bucket_mb` не меняем.
- Safety-правила: hysteresis/rollback пока planned; уже есть rate-limit по `min_interval_s`; удерживаем hold-time/cooldown и freeze window после последнего изменения.
- Ожидаемый эффект: снижение лишних действий, меньше oscillations, стабильный baseline.

### DRIFT-RETUNE
- Режим: медленный дрейф качества/стабильности без аварийного поведения.
- Сигналы детекта: устойчивый `drift`; наблюдаемо растут `p95/p99 step-time` или растёт вариативность шага, при этом нет критического `burst` и нет тяжёлого `gpu_saturated`.
- Аккорд (вектор изменений): `grad_accum_steps` вверх, `microbatch_size` вниз для компенсации; при необходимости мягко `concurrency` вниз; остальные knobs без резких изменений. Инвариант `global_batch ~= microbatch_size * grad_accum_steps * world_size` обязателен, компенсация через `microbatch_size`.
- Safety-правила: hold-time/cooldown обязательны; clamp по min/max для каждой ручки; ограничение `max delta` за шаг; freeze window после изменения. Честно: rollback и полноценная hysteresis planned, в работе уже есть `min_interval_s`.
- Ожидаемый эффект: time-to-stable вниз, oscillations вниз, предсказуемее tail latency.

### BURST-ABSORB
- Режим: короткие всплески задержек и нестабильный хвост по step-time.
- Сигналы детекта: `burst`; метрики `p95/p99 step-time` скачут, tail latency растёт, возможны пики `GPU idle` из-за неравномерной подачи.
- Аккорд (вектор изменений): `dataloader_prefetch_factor` вверх в лимитах, `concurrency` вниз при перегреве очередей, опционально `microbatch_size` вниз с компенсацией через `grad_accum_steps` вверх; `dataloader_num_workers` только в паспортных рамках.
- Safety-правила: clamp min/max, `max delta` за шаг, cooldown/freeze window; запрет на частое "дребезжание" между соседними значениями. Честно: rollback/hysteresis planned, есть рабочий rate-limit `min_interval_s`.
- Ожидаемый эффект: tail latency вниз, меньше burst oscillations, стабильнее throughput.

### INPUT-STRAGGLER
- Режим: деградация input-пайплайна и неравномерность воркеров.
- Сигналы детекта: `straggler`; наблюдаемо растут `straggler score`, `p99 step-time`, увеличивается разброс по batch-ready времени, может расти `GPU idle`.
- Аккорд (вектор изменений): `dataloader_num_workers` вверх в рамках лимитов, `dataloader_prefetch_factor` вверх умеренно, `concurrency` вниз при перегрузке input-цепочки; `timeout_ms` по умолчанию только propose-only. `microbatch_size`/`grad_accum_steps` меняем только при необходимости и с инвариантом `global_batch`.
- Safety-правила: apply по умолчанию `auto=propose`; для "хрупких" актуаторов (`timeout_ms`, агрессивные worker-изменения) apply только если паспорт явно разрешает; clamp/cooldown/`max delta`/freeze window обязательны; rollback/hysteresis пока planned, `min_interval_s` уже есть.
- Ожидаемый эффект: ниже straggler tail, меньше простоев GPU, более ровный step cadence.

### RECOVER-RELOCK
- Режим: восстановление после инцидента и возврат к стабильному профилю.
- Сигналы детекта: после `burst`/`straggler`/`gpu_saturated` метрики стабилизируются (нормализуются `p95/p99 step-time`, падает `straggler score`, `GPU idle` возвращается в коридор).
- Аккорд (вектор изменений): аккуратный возврат `concurrency`, `dataloader_prefetch_factor`, `dataloader_num_workers`, `microbatch_size`, `grad_accum_steps` к паспортному baseline; `timeout_ms` - propose-only по умолчанию; `comm_bucket_mb` не трогаем в safe v1.
- Safety-правила: ступенчатый relock с cooldown и freeze window; clamp и `max delta` сохраняются; rollback/hysteresis planned, есть `min_interval_s`.
- Ожидаемый эффект: time-to-stable вниз после инцидента, меньше повторных срывов, мягкий возврат к рабочему режиму.

## Advanced chords (Off by default)
### COMM-CONGESTION
Требует телеметрию коммуникаций: `allreduce timing`, `comm latency`, признаки network congestion по шагам. Без этих сигналов опасно менять `comm_bucket_mb` и связанные ручки, потому что можно перепутать compute/input узкое место с сетевым и ухудшить ситуацию.

### NEAR-HANG/TIMEOUT-GUARD
Требует отдельные сигналы watchdog: предупреждения о near-timeout, stalled step, рост retry/timeout-path. Без этой телеметрии опасно "лечить" через `timeout_ms` и снижение параллелизма: можно замаскировать реальную неисправность и увеличить время деградации.

## Default bans v1
По умолчанию запрещено автоприменение для:
- tempo/pacing;
- placement/reschedule;
- timeout/retry policy.

Если `timeout_ms` фигурирует в policy, статус по умолчанию:
- `propose-only`;
- `apply` только при явном разрешении в паспорте.

## Связанные документы
- `docs/PASSPORTS.md`
- `docs/product.md`
- `docs/SNAPSHOT.md`
