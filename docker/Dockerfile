FROM python:3.11-slim

WORKDIR /app

# 컨텍스트가 레포 루트이므로 바로 복사 가능
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 앱 코드 복사 (레포 루트의 app/ → 컨테이너 /app/app)
COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]