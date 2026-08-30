# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 生成统一 API、Worker 与定时任务镜像，减少旧电脑虚拟机维护差异。
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /app/storage
EXPOSE 8000

