import os
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import yt_dlp

app = FastAPI()

# Configuración para permitir que tu Vercel se comunique con este servidor
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOAD_DIR = "temporal_downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

class VideoRequest(BaseModel):
    url: str

def delete_file(path: str):
    """Borra el video del servidor después de enviarlo para no llenar la memoria"""
    if os.path.exists(path):
        os.remove(path)

@app.post("/descargar")
async def descargar_video(request: VideoRequest, background_tasks: BackgroundTasks):
    # Configuración maestra de yt-dlp con todos los parches
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title).50s.%(ext)s'), # Límite de 50 letras (Parche Facebook)
        'quiet': False,
        'cookiefile': 'cookies.txt', # Pasaporte antibots (Parche YouTube)
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extraer info y descargar
            info = ydl.extract_info(request.url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Asegurarnos de que envíe el .mp4 final después de que FFmpeg los una
            base, _ = os.path.splitext(filename)
            final_filename = f"{base}.mp4"
            
            if not os.path.exists(final_filename):
                final_filename = filename

        # Programar el borrado y enviar el archivo al usuario
        background_tasks.add_task(delete_file, final_filename)
        return FileResponse(
            path=final_filename, 
            filename=os.path.basename(final_filename), 
            media_type='video/mp4'
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
