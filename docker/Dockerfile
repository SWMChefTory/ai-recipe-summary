# 베이스 이미지
FROM python:3.11-slim

WORKDIR /app

# requirements.txt 복사
COPY ../requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# yt-dlp 최신 버전 설치
RUN pip install --no-cache-dir -U yt-dlp

# 애플리케이션 복사
COPY app ./app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
