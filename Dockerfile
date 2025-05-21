FROM python:3.11-slim

# sistēmas bibliotēkas
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# vides mainīgie
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRAMES_DIR=/app/frames \
    VIOLATIONS_DIR=/app/violations \
    YOLO_CONFIG_DIR=/app/.ultralytics

WORKDIR /app

# python-dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# projekta pirmkods
COPY . .

RUN mkdir -p "$FRAMES_DIR" "$VIOLATIONS_DIR" "$YOLO_CONFIG_DIR"

# drošības nolūkos (nav root lietotājs)
RUN adduser -u 5678 --disabled-password --gecos "" appuser \
 && chown -R appuser /app
USER appuser

EXPOSE 8000

# ieejas punkts
CMD ["python", "-m", "web_app.app"]