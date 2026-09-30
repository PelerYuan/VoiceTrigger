FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    VOICE_DEVICE=cuda \
    VOICE_COMPUTE_TYPE=int8_float32 \
    VOICE_MODEL_CACHE=/models \
    VOICE_EVENTS_FILE=/events/triggers.jsonl

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv ffmpeg libportaudio2 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
COPY config.example.toml ./config.toml
RUN useradd --uid 10001 --create-home listener \
    && mkdir /models /events \
    && chown listener:listener /models /events
USER listener
ENTRYPOINT ["voice-trigger"]
CMD ["run", "--config", "/app/config.toml"]
