from __future__ import annotations

from typing import Iterable

from modekeeper.policy.actions import Action

_SYMPTOM_WEIGHTS = {
    "drift": 2,
    "straggler": 2,
    "burst": 1,
    "gpu_saturated": 2,
}

_RECOMMENDATIONS = {
    "drift": [
        "Перейдите на CLOSED_LOOP: удержание throughput при дрейфе",
        "Проверьте изменение профиля батча/данных",
    ],
    "straggler": [
        "Проверьте dataloader_* (workers/prefetch)",
        "Проверьте timeout_ms",
        "Снизьте concurrency при tail-latency",
    ],
    "burst": [
        "Проверьте concurrency и очереди",
        "Увеличьте prefetch/worker если CPU позволяет",
    ],
    "gpu_saturated": [
        "GPU упёрлась в util/memory: снизьте microbatch_size",
        "Проверьте утечки/фрагментацию памяти, пики аллокаций",
        "Если нужно удержать effective batch — компенсируйте grad_accum_steps",
    ],
}


def _is_symptom_active(value: object) -> bool:
    if value is True:
        return True
    if isinstance(value, dict):
        detected = value.get("detected") is True
        score = value.get("score", 0)
        severity = value.get("severity", 0)
        return detected or score > 0 or severity > 0
    return False


def _active_symptoms(signals: dict) -> list[str]:
    active: list[str] = []
    for symptom in _SYMPTOM_WEIGHTS:
        if _is_symptom_active(signals.get(symptom)):
            active.append(symptom)
    return active


def _risk_level(score: int) -> str:
    if score == 0:
        return "low"
    if score <= 2:
        return "medium"
    return "high"


def _plural_ru(n: int, one: str, few: str, many: str) -> str:
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
        return few
    return many


def summarize_observe(signals: dict) -> dict:
    active = _active_symptoms(signals)
    risk_score = sum(_SYMPTOM_WEIGHTS[s] for s in active)
    recommendations: list[str] = []
    for symptom in active:
        recommendations.extend(_RECOMMENDATIONS.get(symptom, []))
    if not recommendations:
        recommendations.append("Блокирующих симптомов не обнаружено за окно наблюдения")
    return {
        "money_leak_risk": _risk_level(risk_score),
        "top_symptoms": active,
        "estimated_impact": "unknown",
        "recommendations": recommendations,
    }


def summarize_decision(signals: dict, proposed: list[Action]) -> list[str]:
    active = _active_symptoms(signals)
    summary: list[str] = []
    if active:
        summary.append(f"Сигналы: {', '.join(active)}.")
    else:
        summary.append("Сигналы: drift/straggler/burst/gpu_saturated не обнаружены.")

    if proposed:
        n = len(proposed)
        summary.append(f"Предложено {n} {_plural_ru(n, 'действие', 'действия', 'действий')} для устранения симптомов.")
        reasons = _unique_reasons(proposed)
        if reasons:
            summary.append(f"Причины действий: {', '.join(reasons)}.")
    else:
        summary.append("Действия не предложены: нет триггерящих сигналов.")

    return summary[:3]


def _unique_reasons(proposed: Iterable[Action]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for action in proposed:
        reason = action.reason
        if reason and reason not in seen:
            seen.add(reason)
            ordered.append(reason)
    return ordered
