from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import yt_dlp
import os
import uuid
import re

app = FastAPI()

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
    """Crea una copia temporal limpia (formato Linux LF) de cookies.txt."""
    if os.path.exists("cookies.txt") and os.path.getsize("cookies.txt") > 10:
        temp_cookie = os.path.join(TEMP_DIR, f"cookie_{uuid.uuid4().hex}.txt")
        with open("cookies.txt", "rb") as f_in:
            contenido = f_in.read().replace(b"\r\n", b"\n")
        with open(temp_cookie, "wb") as f_out:
            f_out.write(contenido)
        return temp_cookie
    return None

def borrar_archivo(ruta: str):
    try:
        if ruta and os.path.exists(ruta):
            os.remove(ruta)
    except Exception:
        pass

def ejecutar_ytdlp(url: str, opciones_base: dict, descargar: bool):
    """Prueba distintas estrategias de cliente para evadir bloqueos de YouTube, X y TikTok."""
    cookie_temp = obtener_cookie_temp()
    estrategias = []

    # Estrategia 1: Clientes móviles/VR sin cookies (no sufren bloqueo SABR de IP en YouTube)
    opts_movil = opciones_base.copy()
    opts_movil["extractor_args"] = {
        "youtube": {
            "player_client": ["android_vr", "ios", "mweb", "tv_embedded"]
        }
    }
    estrategias.append(("Clientes Móviles/VR", opts_movil))

    # Estrategia 2: Con cookies.txt usando clientes TV, Creator y Mobile Web
    if cookie_temp:
        opts_cookies_tv = opciones_base.copy()
        opts_cookies_tv["cookiefile"] = cookie_temp
        opts_cookies_tv["extractor_args"] = {
            "youtube": {
                "player_client": ["tv", "web_creator", "mweb", "web"]
            }
        }
        estrategias.append(("Cookies + TV/Creator", opts_cookies_tv))

        # Estrategia 3: Con cookies.txt estándar (ideal para X/Twitter, TikTok, Instagram)
        opts_cookies_std = opciones_base.copy()
        opts_cookies_std["cookiefile"] = cookie_temp
        estrategias.append(("Cookies Estándar", opts_cookies_std))

    # Estrategia 4: Estándar sin cookies (para TikTok y webs externas)
    estrategias.append(("Estándar Directo", opciones_base.copy()))

    errores = []
    try:
        for nombre_est, opts in estrategias:
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=descargar)
                    if info:
                        print(f"Éxito usando estrategia: {nombre_est}")
                        return info
            except Exception as e:
                print(f"Fallo en estrategia [{nombre_est}]: {str(e)}")
                errores.append(str(e))
                continue
        raise Exception(errores[0] if errores else "No se pudo extraer el video.")
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
        "format": "bestvideo*+bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "geo_bypass": True,
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
    url = request.url.strip()
    file_id = uuid.uuid4().hex
    output_template = os.path.join(TEMP_DIR, f"{file_id}.%(ext)s")

    ydl_opts = {
        "format": "bestvideo*[height<=1080]+bestaudio/best[height<=1080]/bestvideo*+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "geo_bypass": True,
        "postprocessors": [{
            "key": "FFmpegVideoRemuxer",
            "preferedformat": "mp4",
        }],
    }

    try:
        info = ejecutar_ytdlp(url, ydl_opts, descargar=True)
        titulo_limpio = limpiar_nombre(info.get("title", "Video_MP4"))

        archivo_final = os.path.join(TEMP_DIR, f"{file_id}.mp4")
        if not os.path.exists(archivo_final):
            for nombre in os.listdir(TEMP_DIR):
                if nombre.startswith(file_id) and not nombre.endswith(".txt"):
                    archivo_final = os.path.join(TEMP_DIR, nombre)
                    break

        if not os.path.exists(archivo_final):
            raise Exception("El archivo de video no se pudo empaquetar.")

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
