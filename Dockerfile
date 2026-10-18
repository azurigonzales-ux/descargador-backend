FROM python:3.11-slim

# Instalar ffmpeg, nodejs (necesario para descifrar firmas de YouTube) y certificados
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg nodejs ca-certificates && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# Instalar dependencias y la versión más reciente (nightly/pre-release) de yt-dlp con soporte anti-bloqueo
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -U --pre "yt-dlp[default,curl-cffi]"

COPY . .

EXPOSE 8000

# Al arrancar, asegura tener el último parche de yt-dlp y levanta el servidor
CMD ["sh", "-c", "pip install -q -U --pre 'yt-dlp[default,curl-cffi]' && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
