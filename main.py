import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import yt_dlp

app = FastAPI()

# Permitir que React se comunique con la API de Python sin bloqueos de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Crear directorio temporal para procesar los videos
DOWNLOAD_DIR = os.path.join(os.getcwd(), "temporal_downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

class VideoRequest(BaseModel):
    url: str

@app.post("/descargar")
async def descargar_video(request: VideoRequest):
    url = request.url
    if not url:
        raise HTTPException(status_code=400, detail="URL no válida.")

    # Configuración estricta para descargar la calidad más alta de video y audio
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',  # FFmpeg fusionará los flujos automáticamente aquí
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'quiet': False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info_dict)
            
            # Asegurar la extensión correcta tras la unión de pistas
            filename_mp4 = os.path.splitext(filename)[0] + ".mp4"
            path_final = filename_mp4 if os.path.exists(filename_mp4) else filename

        # Devolver el archivo directamente para que el navegador dispare la descarga
        return FileResponse(
            path=path_final,
            media_type="video/mp4",
            filename=os.path.basename(path_final)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar: {str(e)}")