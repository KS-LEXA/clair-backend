from __future__ import annotations

# 카테고리별 중요도 가중치
CATEGORY_WEIGHTS: dict[str, float] = {
    "payment":         1.2,
    "liability":       1.8,
    "termination":     1.5,
    "confidentiality": 1.0,
    "auto_renewal":    1.3,
    "renewal":         1.3,
    "penalty":         1.7,
    "ip":              1.6,
    "non_compete":     1.4,
    "unilateral":      1.3,
}

# 위험 레벨 기본 점수
LEVEL_SCORES: dict[str, int] = {
    "low":    4,
    "medium": 10,
    "high":   20,
}

BASE_SCORE = 100


def compute_safety_score(risk_clauses: list) -> dict:
    """
    계약서 안전 점수 계산.

    Returns:
        {
            "score": int,
            "deductions": list,
            "total_deduction": int
        }
    """
    if not risk_clauses:
        return {"score": 95, "deductions": [], "total_deduction": 0}

    deductions = []
    total_deduction = 0

    for rc in risk_clauses:
        level = rc.risk_level.value.lower() if hasattr(rc.risk_level, "value") else str(rc.risk_level).lower()
        level_score = LEVEL_SCORES.get(level, 10)
        category_weight = CATEGORY_WEIGHTS.get(rc.risk_type, 1.0)
        severity_score = rc.severity_score if rc.severity_score else 5
        confidence = rc.confidence if rc.confidence else 0.7

        deduction = round(level_score * category_weight * (severity_score / 10) * confidence)
        total_deduction += deduction

        deductions.append({
            "title": rc.risk_type,
            "category": rc.risk_type,
            "risk_level": level,
            "deduction": deduction,
            "reason": (
                f"{level.upper()} 위험 / "
                f"심각도 {severity_score} / "
                f"신뢰도 {confidence:.2f}"
            ),
        })

    # 고위험 조항 3개 이상 추가 패널티
    high_count = sum(
        1 for rc in risk_clauses
        if (rc.risk_level.value if hasattr(rc.risk_level, "value") else str(rc.risk_level)).lower() == "high"
    )
    if high_count >= 3:
        extra = 10
        total_deduction += extra
        deductions.append({
            "title": "복수 고위험 조항",
            "category": "global",
            "risk_level": "high",
            "deduction": extra,
            "reason": "고위험 조항이 3개 이상 존재",
        })

    final_score = max(25, BASE_SCORE - total_deduction)

    return {
        "score": final_score,
        "deductions": deductions,
        "total_deduction": total_deduction,
    }
