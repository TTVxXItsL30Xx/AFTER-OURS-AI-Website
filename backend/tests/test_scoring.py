from datetime import datetime, timedelta, timezone

from app.services.scoring import calculate_opportunity_score


def test_score_is_bounded_and_has_explainable_signals():
    score, breakdown = calculate_opportunity_score(published_at=datetime.now(timezone.utc) - timedelta(hours=4), views=25_000, likes=2_000, comments=160, creator_baseline=10_000)
    assert 0 <= score <= 100
    assert breakdown["views_per_hour"] == 6250.0
    assert set(["velocity", "engagement", "freshness", "reach", "creator_baseline"]).issubset(breakdown)


def test_missing_metrics_are_safe():
    score, breakdown = calculate_opportunity_score(published_at=None, views=None, likes=None, comments=None)
    assert 0 <= score <= 100
    assert breakdown["engagement_rate"] == 0

