from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from urllib.parse import quote
import unicodedata
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
    """Elimina emojis, notas musicales (♪) y símbolos que rompen las cabeceras HTTP."""
    if not titulo:
        return "video_descargado"
    normalizado = unicodedata.normalize("NFKD", str(titulo))
    solo_ascii = normalizado.encode("ascii", "ignore").decode("ascii")
    limpio = re.sub(r'[\\/*?:"<>|#\r\n\t]', "", solo_ascii)
    limpio = re.sub(r"\s+", " ", limpio).strip()[:80]
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
    cookie_temp = obtener_cookie_temp()
    
    # Habilitar explícitamente Deno y Node para descifrar los formatos MP4
    opciones_base["js_runtimes"] = {"deno": {}, "node": {}}
    opciones_base["remote_components"] = ["ejs:github"]

    estrategias = []

    if cookie_temp:
        # Estrategia 1: Cookies + clientes Web Safari / TV / Creator
        opts_1 = opciones_base.copy()
        opts_1["cookiefile"] = cookie_temp
        opts_1["extractor_args"] = {
            "youtube": {
                "player_client": ["web_safari", "tv_simply", "tv", "web_creator", "mweb", "web"]
            }
        }
        estrategias.append(("Cookies + Multi-Cliente JS", opts_1))

        # Estrategia 2: Cookies estándar (ideal para X/Twitter, TikTok, Instagram, Facebook)
        opts_2 = opciones_base.copy()
        opts_2["cookiefile"] = cookie_temp
        estrategias.append(("Cookies Estándar", opts_2))

    # Estrategia 3: Sin cookies con clientes móviles/embebidos
    opts_3 = opciones_base.copy()
    opts_3["extractor_args"] = {
        "youtube": {
            "player_client": ["ios", "android_vr", "tv_embedded", "web_safari"]
        }
    }
    estrategias.append(("Clientes Móviles Sin Cookies", opts_3))

    errores = []
    try:
        for nombre_est, opts in estrategias:
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=descargar)
                    if info:
                        print(f"ÉXITO con estrategia: {nombre_est}")
                        return info
            except Exception as e:
                print(f"Fallo en [{nombre_est}]: {str(e)}")
                errores.append(f"[{nombre_est}]: {str(e)}")
                continue
        raise Exception(" | ".join(errores))
    finally:
        if cookie_temp:
            borrar_archivo(cookie_temp)

def respaldo_pytubefix_info(url: str):
    from pytubefix import YouTube
    for cliente in ["WEB", "MWEB", "IOS", "TV", "ANDROID_VR"]:
        try:
            yt = YouTube(url, client=cliente)
            return {
                "titulo": yt.title or "Video de YouTube",
                "miniatura": yt.thumbnail_url or "",
                "duracion": yt.length or 0,
                "plataforma": "YouTube",
                "url_original": url
            }
        except Exception as e:
            print(f"Fallo respaldo info [{cliente}]: {e}")
            continue
    raise Exception("No se pudo extraer con ningún motor.")

def respaldo_pytubefix_descarga(url: str, file_id: str):
    from pytubefix import YouTube
    for cliente in ["WEB", "MWEB", "IOS", "TV", "ANDROID_VR"]:
        try:
            yt = YouTube(url, client=cliente)
            stream = yt.streams.filter(progressive=True, file_extension="mp4").order_by("resolution").desc().first()
            if not stream:
                stream = yt.streams.filter(file_extension="mp4").first()
            if stream:
                ruta = stream.download(output_path=TEMP_DIR, filename=f"{file_id}.mp4")
                return ruta, yt.title
        except Exception as e:
            print(f"Fallo respaldo descarga [{cliente}]: {e}")
            continue
    raise Exception("No se pudo descargar el archivo con el motor de respaldo.")

@app.get("/")
def estado_servidor():
    return {"status": "online", "mensaje": "Servidor activo y listo"}

@app.post("/api/descargar")
async def obtener_info_video(request: VideoRequest):
    url = request.url.strip()
    if not url:
        return JSONResponse(status_code=400, content={"detail": "URL vacía"})

    ydl_opts = {
        "format": "bv*+ba/b",
        "quiet": False,
        "no_warnings": False,
        "noplaylist": True,
        "geo_bypass": True,
        "ignore_no_formats_error": True,
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
    except Exception as e_ytdlp:
        if "youtube.com" in url or "youtu.be" in url:
            try:
                return respaldo_pytubefix_info(url)
            except Exception:
                pass
        return JSONResponse(
            status_code=400,
            content={"detail": f"No se pudo procesar el enlace: {str(e_ytdlp)}"}
        )

@app.post("/api/preparar-archivo")
async def preparar_archivo(request: VideoRequest):
    url = request.url.strip()
    file_id = uuid.uuid4().hex
    output_template = os.path.join(TEMP_DIR, f"{file_id}.%(ext)s")

    ydl_opts = {
        "format": "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
        "geo_bypass": True,
        "postprocessors": [{
            "key": "FFmpegVideoRemuxer",
            "preferedformat": "mp4",
        }],
    }

    try:
        try:
            info = ejecutar_ytdlp(url, ydl_opts, descargar=True)
            titulo_limpio = limpiar_nombre(info.get("title", "Video_MP4"))
        except Exception as e_primario:
            if "youtube.com" in url or "youtu.be" in url:
                print("Activando motor de respaldo pytubefix para la descarga...")
                _, titulo_raw = respaldo_pytubefix_descarga(url, file_id)
                titulo_limpio = limpiar_nombre(titulo_raw)
            else:
                raise e_primario

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

    # Sanitizar el nombre en ASCII puro y codificar versión UTF-8 segura para cabeceras HTTP
    base_nombre = nombre[:-4] if nombre.lower().endswith(".mp4") else nombre
    nombre_ascii = f"{limpiar_nombre(base_nombre)}.mp4"
    nombre_utf8 = quote(f"{base_nombre}.mp4")

    return FileResponse(
        path=ruta_segura,
        media_type="application/octet-stream",
        filename=nombre_ascii,
        headers={
            "Content-Disposition": f"attachment; filename=\"{nombre_ascii}\"; filename*=UTF-8''{nombre_utf8}"
        }
    )
