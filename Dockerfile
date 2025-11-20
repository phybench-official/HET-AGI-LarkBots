FROM python:3.10-slim

# 复制 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 设置工作目录
WORKDIR /app

# 安装依赖
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

# 复制代码
COPY library/ ./library/
COPY scripts/ ./scripts/

# 创建非 root 用户
RUN useradd -m -u 1000 botuser && \
    mkdir -p /app/configs && \
    chown -R botuser:botuser /app

USER botuser

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app"

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s \
    CMD pgrep -f "start_robots.py" || exit 1

CMD ["python", "scripts/start_robots.py"]
