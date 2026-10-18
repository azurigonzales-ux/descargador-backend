from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import yt_dlp
import os
import uuid
import shutil
import re

app = FastAPI()

# Configuración CORS compatible con cualquier dominio de Vercel y móviles
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_DIR = "/tmp/descargas_videos"
os.makedirs(TEMP_DIR, exist_ok=True)

class VideoRequest(BaseModel):
    url: str

def limpiar_nombre(titulo: str) -> str:
    limpio = re.sub(r'[\\/*?:"<>|]', "", titulo)
    limpio = limpio.strip()[:80]
    return limpio if limpio else "video_descargado"

def obtener_cookie_temp():
    """Crea una copia temporal de cookies.txt para que yt-dlp no corrompa el original."""
    if os.path.exists("cookies.txt"):
        temp_cookie = os.path.join(TEMP_DIR, f"cookie_{uuid.uuid4().hex}.txt")
        shutil.copy("cookies.txt", temp_cookie)
        return temp_cookie
    return None

def borrar_archivo(ruta: str):
    try:
        if ruta and os.path.exists(ruta):
            os.remove(ruta)
    except Exception:
        pass

def ejecutar_ytdlp(url: str, opciones_base: dict, descargar: bool):
    """Intenta con cookies primero y, si la plataforma bloquea, usa clientes móviles de respaldo."""
    cookie_temp = obtener_cookie_temp()
    intentos = []

    # Intento 1: Con cookies.txt (si existe) y cliente web/móvil
    if cookie_temp:
        opts1 = opciones_base.copy()
        opts1["cookiefile"] = cookie_temp
        intentos.append(opts1)

    # Intento 2: Sin cookies, emulando cliente nativo iOS/Android/Web
    opts2 = opciones_base.copy()
    opts2["extractor_args"] = {
        "youtube": {
            "player_client": ["ios", "android", "mweb", "web"]
        }
    }
    intentos.append(opts2)

    ultimo_error = None
    try:
        for opts in intentos:
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(url, download=descargar)
            except Exception as e:
                ultimo_error = e
                continue
        raise ultimo_error
    finally:
        if cookie_temp:
            borrar_archivo(cookie_temp)

@app.get("/")
def estado_servidor():
    return {"status": "online", "mensaje": "Servidor activo y listo"}

@app.post("/api/descargar")
async def obtener_info_video(request: VideoRequest):
    url = request.url.strip()
    if not url:
        return JSONResponse(status_code=400, content={"detail": "URL vacía"})

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        },
    }

    try:
        info = ejecutar_ytdlp(url, ydl_opts, descargar=False)
        return {
            "titulo": info.get("title", "Video listo para descargar"),
            "miniatura": info.get("thumbnail", ""),
            "duracion": info.get("duration", 0),
            "plataforma": info.get("extractor_key", "Web"),
            "url_original": url
        }
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"detail": f"No se pudo procesar el enlace: {str(e)}"}
        )

@app.post("/api/preparar-archivo")
async def preparar_archivo(request: VideoRequest):
    """Descarga y une el video en MP4 dentro del servidor para enviarlo listo al teléfono/PC."""
    url = request.url.strip()
    file_id = uuid.uuid4().hex
    output_template = os.path.join(TEMP_DIR, f"{file_id}.%(ext)s")

    ydl_opts = {
        "format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        },
    }

    try:
        info = ejecutar_ytdlp(url, ydl_opts, descargar=True)
        titulo_limpio = limpiar_nombre(info.get("title", "Video_MP4"))

        # Localizar el archivo generado
        archivo_final = os.path.join(TEMP_DIR, f"{file_id}.mp4")
        if not os.path.exists(archivo_final):
            for nombre in os.listdir(TEMP_DIR):
                if nombre.startswith(file_id):
                    archivo_final = os.path.join(TEMP_DIR, nombre)
                    break

        if not os.path.exists(archivo_final):
            raise Exception("El archivo de video no se pudo generar.")

        return {
            "file_id": os.path.basename(archivo_final),
            "filename": f"{titulo_limpio}.mp4"
        }
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"detail": f"Error al empaquetar el video: {str(e)}"}
        )

@app.get("/api/bajar/{file_name}")
async def bajar_archivo(file_name: str, nombre: str = "Video.mp4", background_tasks: BackgroundTasks = None):
    """Entrega el archivo forzando al navegador móvil y de escritorio a guardarlo en Descargas."""
    ruta_segura = os.path.join(TEMP_DIR, os.path.basename(file_name))
    if not os.path.exists(ruta_segura):
        raise HTTPException(status_code=404, detail="El archivo expiró o no existe.")

    if background_tasks:
        background_tasks.add_task(borrar_archivo, ruta_segura)

    return FileResponse(
        path=ruta_segura,
        media_type="application/octet-stream",
        filename=nombre,
        headers={
            "Content-Disposition": f'attachment; filename="{nombre}"'
        }
    )
