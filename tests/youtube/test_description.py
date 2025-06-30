import os
from unittest.mock import MagicMock, patch

import pytest

from app.services.youtube import get_youtube_description


def test_env_key_missing(monkeypatch):
    """환경변수 GOOGLE_API_KEY가 없을 때 에러 메시지를 반환하는지 테스트"""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    result = get_youtube_description("abc123")
    assert result == "ERROR: GOOGLE_API_KEY가 설정되지 않음"


@patch("app.services.youtube.requests.get")
def test_video_found(mock_get, monkeypatch):
    """정상적인 video ID로 설명란을 잘 가져오는지 테스트"""
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "items": [{"snippet": {"description": "This is the description"}}]
    }
    mock_get.return_value = mock_resp

    result = get_youtube_description("abc123")
    assert result == "This is the description"


@patch("app.services.youtube.requests.get")
def test_video_not_found(mock_get, monkeypatch):
    """video ID가 잘못됐을 때 에러 메시지를 반환하는지 테스트"""
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"items": []}
    mock_get.return_value = mock_resp

    result = get_youtube_description("abc123")
    assert result.startswith("ERROR: video ID가 잘못됐거나")


@patch("app.services.youtube.requests.get")
def test_response_missing_snippet(mock_get, monkeypatch):
    """응답에 snippet 키가 없을 때 예외 처리하는지 테스트"""
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"items": [{}]}
    mock_get.return_value = mock_resp

    result = get_youtube_description("abc123")
    assert result.startswith("ERROR: 응답에 예상된 키 없음")


@patch("app.services.youtube.requests.get")
def test_response_not_json(mock_get, monkeypatch):
    """응답에 필요한 키들이 아예 없는 경우 예외 처리 테스트"""
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"kind": "youtube#video"}
    mock_get.return_value = mock_resp

    result = get_youtube_description("abc123")
    assert result.startswith("ERROR: 응답에 예상된 키 없음")
