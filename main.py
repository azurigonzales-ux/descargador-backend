from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import yt_dlp
import httpx
from urllib.parse import quote
import os

app = FastAPI()

# Permite que solo tu Vercel se conecte con este backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://descargador-frontend.vercel.app"], # <-- AQUÍ ESTÁ EL CAMBIO CLAVE
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class VideoRequest(BaseModel):
    url: str

@app.post("/api/descargar")
async def extraer_info(request: VideoRequest):
    ydl_opts = {
        'format': 'best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }
    
    # IMPORTANTE: Esto lee el archivo de cookies para evitar el bloqueo de YouTube
    if os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(request.url, download=False)
            
            video_url = info.get('url')
            if not video_url and 'formats' in info:
                formatos_validos = [f for f in info['formats'] if f.get('vcodec') != 'none' and f.get('url')]
                if formatos_validos:
                    video_url = formatos_validos[-1].get('url')

            return {
                "titulo": info.get('title', 'Video'),
                "url_directa": video_url,
                "miniatura": info.get('thumbnail', '')
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/forzar-descarga")
async def forzar_descarga(url: str, titulo: str = "video"):
    """Este endpoint puentea el video para obligar al celular a descargarlo."""
    async def stream_video():
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", url, follow_redirects=True) as response:
                async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                    yield chunk

    headers = {
        'Content-Disposition': f'attachment; filename="{quote(titulo)}.mp4"'
    }
    return StreamingResponse(stream_video(), media_type="video/mp4", headers=headers)
