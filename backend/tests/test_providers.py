from app.services.providers import _iso_duration_seconds


def test_youtube_iso_duration_parser():
    assert _iso_duration_seconds("PT1H2M3S") == 3723
    assert _iso_duration_seconds("PT42S") == 42
    assert _iso_duration_seconds("invalid") == 0

