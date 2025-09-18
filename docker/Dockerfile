# 베이스 이미지: Python 3.11
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# requirements.txt 복사 및 설치
COPY ./requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# yt-dlp 최신 버전 설치
RUN pip install --no-cache-dir -U yt-dlp

# 전체 애플리케이션 복사
COPY ./app ./app

# FastAPI 실행 명령어
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]