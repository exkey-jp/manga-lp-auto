# 漫画LP 自動制作 Webアプリ（リポジトリのルートを build context にする）
#   docker build -f webapp/Dockerfile -t manga-lp-webapp .
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 DATA_DIR=/data PORT=8080
RUN apt-get update && apt-get install -y --no-install-recommends fonts-noto-cjk && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY webapp/requirements.txt webapp/requirements.txt
RUN pip install --no-cache-dir -r webapp/requirements.txt && playwright install --with-deps chromium
COPY . .
WORKDIR /app/webapp
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
