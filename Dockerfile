FROM python:3.11-slim

# Copiar Deno oficial (motor JS requerido por yt-dlp para descifrar formatos de YouTube)
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno

# Instalar ffmpeg y nodejs
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg nodejs ca-certificates && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# Instalar dependencias, motor EJS de yt-dlp y motor de respaldo pytubefix
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -U --pre "yt-dlp[default,curl-cffi]" yt-dlp-ejs pytubefix

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
