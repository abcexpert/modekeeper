# Custom Passports (Paid): калибровка, интейк, отчёт

Этот документ описывает **платный** процесс создания *custom* паспорта (`passport.v0`) для конкретного окружения.
Цель: безопасно разрешить **управление аккордами/актуаторами** и (при необходимости) *apply* — **только после verify-ok + лицензии + kill-switch**.

> Важно: это не меняет поведения `closed-loop/run|watch` по умолчанию.  
> Free-режим (`mk passport observe-max`) — **только observe + рекомендации, propose-only**.

---

## 1) Что такое custom passport (paid)

**Custom passport** — это `passport.v0`, который:
- фиксирует *allowed_chords* и *allowed_actuators (hot/cold)* **под конкретное окружение**;
- содержит лимиты/инварианты/гейты безопасности;
- может разрешать apply **только в рамках платной политики** (license gate + verify-ok + kill-switch).

---

## 2) Интейк (минимум входных данных)

### 2.1 Контекст окружения (обязательно)
- Тип окружения: `prod` / `staging` / `r&d`
- SLO: целевые метрики и допустимый риск деградации (например p95/p99 step-time коридор)
- Модель/нагрузка: профиль (batch, seq, датасет/поток), периодичность, ожидания по стабильности
- Платформа: k8s namespace/deployment, способ rollout, RBAC ограничения
- Доступные актуаторы (какие knobs реально есть/поддерживаются)

### 2.2 Данные наблюдения (обязательно)
Минимальный “observe trace” должен позволять:
- детектировать базовые сигналы (stable/incident/burst/drift/straggler) хотя бы **по step_time_ms**
- оценить покрытие (какие поля реально есть)

**Рекомендуется** дополнительно (если есть):
- GPU util / GPU mem util
- latency_ms (если отличается от step_time_ms)
- loss
- worker_latencies_ms (для страгглеров)

> Сырые наблюдения/трейсы могут быть приватными. В отчётах и артефактах “для передачи” — только агрегаты/счётчики, без сырых значений.

---

## 3) Workflow калибровки (paid)

### Шаг 0 — Free preflight (обязателен)
Собрать best-effort покрытие и propose-only рекомендации (без apply):

- Команда: `mk passport observe-max ...`
- Артефакты:
  - `passport_observe_max_latest.json` (passport.v0, gates apply=false, propose_only=true)
  - `observe_max_latest.json` (redacted coverage + recommendation)

Это даёт:
- какие сигналы реально детектируются на ваших данных
- какие chords разумно включать **в propose-only** до платной калибровки
- какие актуаторы/пределы можно предложить “по умолчанию”

### Шаг 1 — Сбор калибровочных данных (paid)
Цель: получить репрезентативные наблюдения (trace) под реальной нагрузкой/паттернами.

Требования:
- достаточная длительность, чтобы увидеть **стабильность** + хотя бы один “эпизод” (burst/drift/straggler) если он характерен
- фиксированная конфигурация (для воспроизводимости)
- прозрачность условий (что менялось, что нет)

### Шаг 2 — Построение custom passport (paid)
На основе калибровки формируется `passport.v0`:
- `allowed_chords`: только те, которые реально поддержаны наблюдаемостью
- `allowed_actuators.hot/cold`: только реально доступные knobs
- `limits`:
  - `cooldown_s`
  - `max_delta_per_step`
  - `relock_stable_intervals`
  - `knob_limits` (min/max на каждый knob)
- `gates`:
  - apply по умолчанию **запрещён**, включение — только при контракте
  - `require_verify_ok=true`
  - `require_kill_switch_off=true`
  - лицензирование apply (paid gate)

### Шаг 3 — Verify-only прогон (обязателен)
Custom passport сначала используется в режиме:
- `plan + verify` (без apply)
- проверка инвариантов/лимитов/детекторов
- контроль симптомов и “дребезга”

### Шаг 4 — Ограниченный apply (только после verify-ok + лицензии)
Если apply входит в контракт:
- включается только после verify-ok
- с kill-switch
- с малым max_delta_per_step и cooldown
- с мониторингом отката

---

## 4) Шаблон отчёта (report template)

### 4.1 Заголовок
- Customer / Project:
- Environment: prod/staging/r&d
- Date:
- Owner:

### 4.2 Входные данные
- Источник наблюдений: file/k8s
- Длительность/объём: sample_count, интервалы (без сырых ts)
- Покрытие полей: список ключей + счётчики non-null

### 4.3 Сигналы (best-effort)
- Какие flags детектированы: stable/incident/burst/drift/straggler/gpu_saturated
- Что НЕ покрыто (missing telemetry)

### 4.4 Рекомендации (propose-only)
- recommended allowed_chords (canonical IDs)
- список “proposals” (chord + propose_only)
- риск (qualitative): money_leak_risk + top_symptoms

### 4.5 Custom passport (paid итог)
- allowed_chords / allowed_actuators.hot/cold
- limits (cooldown/max_delta/relock + knob_limits)
- invariants
- gates (verify-ok, kill-switch, license/apply policy)

### 4.6 План внедрения
- verify-only этап: критерии успеха/пороговые алерты
- ограниченный apply этап: условия включения/выключения, rollback стратегия

### 4.7 Redaction statement
- в отчёте нет: raw samples, paths, k8s identity, raw timestamps
- артефакты для передачи: только агрегаты/паспорт

