from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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

@app.get("/api/descargar")
async def descargar_video(url: str):
    # Opciones antibloqueo para yt-dlp
    ydl_opts = {
        'format': 'best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        }
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Buscar la mejor URL directa del archivo .mp4
            video_url = info.get('url')
            if not video_url and 'formats' in info:
                mejores_formatos = [f for f in info['formats'] if f.get('vcodec') != 'none']
                if mejores_formatos:
                    video_url = mejores_formatos[-1].get('url')

            return {
                "titulo": info.get('title', 'Video sin título'),
                "url_directa": video_url,
                "miniatura": info.get('thumbnail', ''),
                "plataforma": info.get('extractor', 'Desconocida')
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al procesar el video: {str(e)}")
