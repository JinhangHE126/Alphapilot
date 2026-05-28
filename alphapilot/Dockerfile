FROM python:3.12-slim-bookworm

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

WORKDIR /app

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY}

# 系统依赖
RUN apt-get update && \
    apt-get install -y \
    gcc \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 600 --retries 5 -r requirements.txt

# 清除构建期代理
ENV HTTP_PROXY="" \
    HTTPS_PROXY="" \
    NO_PROXY=""

# 复制项目代码
COPY . .

# 创建持久化目录
RUN mkdir -p rag_data data checkpoints

EXPOSE 8000

# 启动 FastAPI
CMD ["uvicorn", "api.main:api", "--host", "0.0.0.0", "--port", "8000"]