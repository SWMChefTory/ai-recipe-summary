from unittest.mock import MagicMock

import pytest

from app.services.summaries import summarize


@pytest.fixture
def fake_subtitles():
    return [{"start": 0.0, "end": 2.0, "text": "양파를 볶아준다."}]

@pytest.fixture
def fake_description():
    return "맛있는 양파볶음을 만드는 영상입니다."


def test_openai_response_success(fake_subtitles, fake_description):
    """요약 결과가 정상적으로 반환되는 경우"""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content='{"summary": "요약입니다"}'))
    ]

    result = summarize(fake_subtitles, fake_description, client=mock_client)
    assert result == '{"summary": "요약입니다"}'


def test_openai_response_empty(fake_subtitles, fake_description):
    """응답 내용이 비어 있는 경우 처리"""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content=''))
    ]

    result = summarize(fake_subtitles, fake_description, client=mock_client)
    assert result == "[요약 결과가 비어 있습니다]"


def test_openai_exception_handling(fake_subtitles, fake_description):
    """OpenAI 클라이언트에서 예외 발생 시 처리"""
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("API 오류")

    result = summarize(fake_subtitles, fake_description, client=mock_client)
    assert result.startswith("[요약 실패:")
