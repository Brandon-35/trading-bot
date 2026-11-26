FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY trader trader
COPY prompts prompts
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1 TZ=Asia/Ho_Chi_Minh
RUN useradd -u 1000 bot && mkdir /data && chown bot /data
USER bot
CMD ["python", "-m", "trader.main"]
