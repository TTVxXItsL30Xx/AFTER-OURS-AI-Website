from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from app.config import settings


@dataclass
class DiscoveryResult:
    external_id: str
    title: str
    creator_external_id: str
    creator_name: str
    source_url: str
    thumbnail_url: str | None = None
    description: str | None = None
    published_at: datetime | None = None
    duration_seconds: int | None = None
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    creator_followers: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class DiscoveryProvider(ABC):
    name: str

    @abstractmethod
    def search(self, query: str, max_results: int, published_after: datetime | None = None) -> list[DiscoveryResult]: ...


def _iso_duration_seconds(value: str) -> int:
    import re
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value or "")
    if not match:
        return 0
    hours, minutes, seconds = (int(item or 0) for item in match.groups())
    return hours * 3600 + minutes * 60 + seconds


class YouTubeDiscoveryProvider(DiscoveryProvider):
    name = "youtube"
    base_url = "https://www.googleapis.com/youtube/v3"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.youtube_api_key
        if not self.api_key:
            raise ValueError("YouTube Discovery is not configured. Add YOUTUBE_API_KEY in Settings.")

    def search(self, query: str, max_results: int, published_after: datetime | None = None) -> list[DiscoveryResult]:
        params: dict[str, Any] = {"key": self.api_key, "part": "snippet", "q": query, "type": "video", "maxResults": max_results, "order": "date"}
        if published_after:
            params["publishedAfter"] = published_after.isoformat().replace("+00:00", "Z")
        with httpx.Client(timeout=20) as client:
            response = client.get(f"{self.base_url}/search", params=params)
            response.raise_for_status()
            items = response.json().get("items", [])
            video_ids = [item["id"]["videoId"] for item in items]
            if not video_ids:
                return []
            detail = client.get(f"{self.base_url}/videos", params={"key": self.api_key, "part": "snippet,statistics,contentDetails", "id": ",".join(video_ids)})
            detail.raise_for_status()
        results: list[DiscoveryResult] = []
        for item in detail.json().get("items", []):
            snippet, stats = item["snippet"], item.get("statistics", {})
            thumb = snippet.get("thumbnails", {}).get("high") or snippet.get("thumbnails", {}).get("default", {})
            results.append(DiscoveryResult(
                external_id=item["id"], title=snippet["title"], creator_external_id=snippet["channelId"], creator_name=snippet["channelTitle"],
                source_url=f"https://www.youtube.com/watch?v={item['id']}", thumbnail_url=thumb.get("url"), description=snippet.get("description"),
                published_at=datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00")), duration_seconds=_iso_duration_seconds(item.get("contentDetails", {}).get("duration", "")),
                views=int(stats["viewCount"]) if "viewCount" in stats else None, likes=int(stats["likeCount"]) if "likeCount" in stats else None,
                comments=int(stats["commentCount"]) if "commentCount" in stats else None, raw=item,
            ))
        return results


@dataclass
class TranscriptResult:
    text: str
    segments: list[dict[str, Any]]
    language: str = "en"


class TranscriptionProvider(ABC):
    name: str
    @abstractmethod
    def transcribe(self, media_path: Path, duration_seconds: float | None) -> TranscriptResult: ...


class MockTranscriptionProvider(TranscriptionProvider):
    name = "mock"
    def transcribe(self, media_path: Path, duration_seconds: float | None) -> TranscriptResult:
        duration = max(15.0, duration_seconds or 60.0)
        chunk = min(20.0, duration / 3)
        segments = [
            {"start": 0.0, "end": chunk, "text": "Mock provider is active. Connect a transcription provider to generate speech-accurate text."},
            {"start": chunk, "end": min(chunk * 2, duration), "text": f"Source file {media_path.name} is ready for the real transcription pipeline."},
            {"start": min(chunk * 2, duration), "end": duration, "text": "This fallback preserves the complete Studio workflow without claiming an AI transcription occurred."},
        ]
        return TranscriptResult(text=" ".join(item["text"] for item in segments), segments=segments)


class AnalysisProvider(ABC):
    name: str
    @abstractmethod
    def suggest_moments(self, transcript: TranscriptResult, duration_seconds: float | None) -> list[dict[str, Any]]: ...


class MockAnalysisProvider(AnalysisProvider):
    name = "mock"
    def suggest_moments(self, transcript: TranscriptResult, duration_seconds: float | None) -> list[dict[str, Any]]:
        duration = max(15.0, duration_seconds or 60.0)
        clip_length = min(45.0, duration)
        starts = sorted(set([0.0, max(0.0, duration / 2 - clip_length / 2), max(0.0, duration - clip_length)]))
        return [{"start_seconds": start, "end_seconds": min(duration, start + clip_length), "score": round(82 - index * 6, 1), "title": f"Candidate moment {index + 1}", "hook": "A sharp opening worth reviewing", "rationale": "Generated by the local fallback analyser; review timing and copy before rendering."} for index, start in enumerate(starts)]


class PublishingProvider(ABC):
    name: str
    @abstractmethod
    def publish(self, clip_path: Path, title: str, caption: str | None) -> dict[str, str]: ...


class UnconfiguredPublishingProvider(PublishingProvider):
    def __init__(self, name: str): self.name = name
    def publish(self, clip_path: Path, title: str, caption: str | None) -> dict[str, str]:
        raise RuntimeError(f"{self.name.title()} publishing is not configured. Connect an official API account first.")


class YouTubePublishingProvider(UnconfiguredPublishingProvider):
    def __init__(self): super().__init__("youtube")


class TikTokPublishingProvider(UnconfiguredPublishingProvider):
    def __init__(self): super().__init__("tiktok")


class InstagramPublishingProvider(UnconfiguredPublishingProvider):
    def __init__(self): super().__init__("instagram")


def get_transcription_provider() -> TranscriptionProvider:
    if settings.transcription_provider == "mock": return MockTranscriptionProvider()
    raise RuntimeError(f"Transcription provider '{settings.transcription_provider}' is not installed")


def get_analysis_provider() -> AnalysisProvider:
    if settings.analysis_provider == "mock": return MockAnalysisProvider()
    raise RuntimeError(f"Analysis provider '{settings.analysis_provider}' is not installed")
