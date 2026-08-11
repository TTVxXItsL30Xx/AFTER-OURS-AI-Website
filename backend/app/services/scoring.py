import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ScoreWeights:
    velocity: float = 0.30
    engagement: float = 0.20
    freshness: float = 0.25
    reach: float = 0.15
    creator_baseline: float = 0.10


def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def calculate_opportunity_score(
    *,
    published_at: datetime | None,
    views: int | None,
    likes: int | None,
    comments: int | None,
    creator_baseline: float | None = None,
    weights: ScoreWeights = ScoreWeights(),
) -> tuple[float, dict[str, float]]:
    now = datetime.now(timezone.utc)
    if published_at and published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_hours = max(1.0, (now - published_at).total_seconds() / 3600) if published_at else 720.0
    safe_views = max(0, views or 0)
    velocity = safe_views / age_hours
    engagement_rate = ((likes or 0) + (comments or 0) * 2) / max(safe_views, 1)
    signals = {
        "velocity": _clamp(math.log10(velocity + 1) / 5 * 100),
        "engagement": _clamp(engagement_rate / 0.12 * 100),
        "freshness": _clamp(100 - (age_hours / (24 * 14) * 100)),
        "reach": _clamp(math.log10(safe_views + 1) / 7 * 100),
        "creator_baseline": _clamp((safe_views / creator_baseline) * 50) if creator_baseline else 50.0,
    }
    weight_map = asdict(weights)
    total_weight = sum(weight_map.values()) or 1
    score = sum(signals[key] * weight_map[key] for key in signals) / total_weight
    breakdown = {**{key: round(value, 2) for key, value in signals.items()}, "age_hours": round(age_hours, 2), "views_per_hour": round(velocity, 2), "engagement_rate": round(engagement_rate, 5)}
    return round(_clamp(score), 1), breakdown

