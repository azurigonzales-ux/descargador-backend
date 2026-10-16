from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp

app = FastAPI()

# Permite que Vercel se conecte con este backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Estructura de los datos que recibe
class VideoRequest(BaseModel):
    url: str

@app.post("/api/descargar")
async def descargar_video(request: VideoRequest):
    # Opciones antibloqueo para yt-dlp
    ydl_opts = {
        'format': 'best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # download=False extrae la info sin descargar el archivo pesado en Render
            info = ydl.extract_info(request.url, download=False)
            
            # Buscar la mejor URL directa del archivo
            video_url = info.get('url')
            if not video_url and 'formats' in info:
                formatos_validos = [f for f in info['formats'] if f.get('vcodec') != 'none' and f.get('url')]
                if formatos_validos:
                    video_url = formatos_validos[-1].get('url')

            return {
                "titulo": info.get('title', 'Video sin título'),
                "url_directa": video_url,
                "miniatura": info.get('thumbnail', '')
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al procesar el video: {str(e)}")
