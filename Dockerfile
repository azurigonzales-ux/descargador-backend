# Usar una imagen oficial de Python ligera
FROM python:3.11-slim

# Instalar FFmpeg en el servidor de la nube (CRUCIAL para la máxima calidad)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean

WORKDIR /app

# Copiar e instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo tu código
COPY . .

# Comando para encender el servidor en la nube
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]