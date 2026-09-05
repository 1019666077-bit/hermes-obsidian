# Hermes×Obsidian API (Phase 5)
# Default: lightweight script organizer. Hermes Agent is optional/advanced.
#
# Build from repo root:
#   docker compose build
#   # or: docker build -f server/Dockerfile -t hermes-obsidian-api .
#
# Optional advanced: mount host ~/.hermes and install hermes-agent separately;
# set ORGANIZE_ENGINE=auto|hermes and provide model API keys.

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r /app/server/requirements.txt

# API + offline organizer + Hermes wrapper + skills (not the full hermes-agent tree)
COPY server/ /app/server/
COPY organize_vault.py /app/organize_vault.py
COPY run_hermes_organize.sh /app/run_hermes_organize.sh
COPY skills/ /app/skills/

RUN chmod +x /app/organize_vault.py /app/run_hermes_organize.sh /app/server/start.sh \
    && mkdir -p /app/server/jobs

# Container default: script engine (Hermes is heavy / optional)
ENV ORGANIZE_ENGINE=script \
    HERMES_TIMEOUT_SEC=240 \
    FREE_QUOTA_LIMIT=5 \
    PYTHONUNBUFFERED=1

WORKDIR /app/server
EXPOSE 8787

# Advanced (optional):
#   -v "$HOME/.hermes:/root/.hermes:ro"
#   install/mount hermes-agent + set ORGANIZE_ENGINE=auto
#   provide WECHAT_APPID / WECHAT_SECRET via env_file for live login

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8787"]
