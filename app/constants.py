"""
애플리케이션 전역 상수 정의
"""

# 오디오 처리 관련 상수
class AudioConfig:
    """오디오 처리 관련 설정"""
    MAX_FILE_SIZE_MB = 25
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
    
    # 압축 설정
    COMPRESSED_SAMPLE_RATE = 16000
    COMPRESSED_CHANNELS = 1
    COMPRESSED_BITRATE = "64k"
    
    # OpenAI Whisper API 설정
    WHISPER_MODEL = "whisper-1"
    DEFAULT_LANGUAGE = "ko"


class YouTubeConfig:
    """YouTube 관련 설정"""
    MAX_VIDEO_DURATION_SECONDS = 3600  # 1시간
    EXTRACTION_RETRY_COUNT = 4
    DEFAULT_LANGUAGE = "ko"
    
    # User-Agent 설정
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"


class AIConfig:
    """AI 모델 관련 설정"""
    DEFAULT_MODEL = "gpt-4o-mini"
    MAX_TOKENS = 4096
    TEMPERATURE = 0.5
    

class CaptionConfig:
    """자막 처리 관련 설정"""
    DEFAULT_PRECISION = 3


# 언어 코드 매핑 (ISO-639-1 형식으로 정규화)
LANGUAGE_MAPPING = {
    # 한국어
    'korean': 'ko',
    'ko-kr': 'ko',
    'korean-kr': 'ko', 
    'korean_kr': 'ko',
    
    # 영어
    'english': 'en',
    'en-us': 'en',
    'en-gb': 'en',
    'english-us': 'en',
    'english-gb': 'en',
    
    # 일본어
    'japanese': 'ja',
    'ja-jp': 'ja',
    
    # 중국어
    'chinese': 'zh',
    'zh-cn': 'zh',
    'zh-tw': 'zh',
    
    # 스페인어
    'spanish': 'es',
    'es-es': 'es',
    'es-mx': 'es',
    
    # 프랑스어
    'french': 'fr',
    'fr-fr': 'fr',
    
    # 독일어
    'german': 'de',
    'de-de': 'de',
    
    # 이탈리아어
    'italian': 'it',
    'it-it': 'it',
    
    # 포르투갈어
    'portuguese': 'pt',
    'pt-br': 'pt',
    'pt-pt': 'pt',
    
    # 러시아어
    'russian': 'ru',
    'ru-ru': 'ru',
    
    # 아랍어
    'arabic': 'ar',
    'ar-sa': 'ar',
    
    # 힌디어
    'hindi': 'hi',
    'hi-in': 'hi',
    
    # 기타 언어들
    'dutch': 'nl',
    'swedish': 'sv',
    'norwegian': 'no',
    'danish': 'da',
    'finnish': 'fi',
    'polish': 'pl',
    'czech': 'cs',
    'hungarian': 'hu',
    'romanian': 'ro',
    'turkish': 'tr',
    'greek': 'el',
    'hebrew': 'he',
    'thai': 'th',
    'vietnamese': 'vi',
    'indonesian': 'id',
    'malay': 'ms',
    'filipino': 'tl',
    'tamil': 'ta',
    'telugu': 'te',
    'bengali': 'bn',
    'gujarati': 'gu',
    'marathi': 'mr',
    'punjabi': 'pa',
    'urdu': 'ur',
}


class ErrorMessages:
    """에러 메시지 상수"""
    # API 관련
    GOOGLE_API_KEY_MISSING = "GOOGLE_API_KEY가 설정되지 않았습니다"
    VIDEO_NOT_FOUND = "영상을 찾을 수 없습니다"  
    RESPONSE_KEY_MISSING = "응답에서 키를 찾을 수 없습니다"
    OPENAI_CLIENT_REQUIRED = "OpenAI 클라이언트가 필요합니다"
    
    # 요약 관련
    SUMMARY_EMPTY = "요약 결과가 비어 있습니다"
    SUMMARY_FAILED = "요약 생성에 실패했습니다"
    
    # 파일 관련
    FILE_TOO_LARGE = "파일 크기가 25MB를 초과합니다"
    FILE_NOT_FOUND = "파일을 찾을 수 없습니다"
    VIDEO_TOO_LONG = "영상이 너무 깁니다"
    COMPRESSION_FAILED = "압축 후에도 파일이 너무 큽니다" 
    
    # 오디오 관련
    AUDIO_SERVICE_NOT_CONFIGURED = "오디오 서비스가 설정되지 않았습니다" 
    