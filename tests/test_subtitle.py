import pytest
from app.services.youtube import get_video_id_from_youtube, download_youtube_subtitles

@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=I3w8zAFa_G4",
    "https://youtu.be/I3w8zAFa_G4",
    "https://www.youtube.com/shorts/I3w8zAFa_G4",
    "https://www.youtube.com/embed/I3w8zAFa_G4",
])
def test_get_video_id_from_youtube_valid_cases(url):
    """유효한 유튜브 링크면 video_id가 정상적으로 반환되어야 한다."""
    assert get_video_id_from_youtube(url) == "I3w8zAFa_G4"

def test_get_video_id_from_youtube_with_invalid_url():
    """유효하지 않은 링크면 None이 반환되어야 한다."""
    # When
    youtube_video_id = get_video_id_from_youtube("https://www.youtube.com/watch?v=")

    # Then
    assert youtube_video_id == None
    

def test_subtitles_exist_success():
    """자막이 존재하는 경우 정상적으로 반환되어야 한다."""

def test_subtitles_multiple_languages_prefers_audio_lang():
    """다국어 자막이 있는 경우, 음성 언어와 일치하는 자막을 우선 선택해야 한다."""

def test_video_unavailable_should_fail():
    """유튜브 링크 형식은 맞지만 영상이 존재하지 않는 경우 예외를 발생시켜야 한다."""
