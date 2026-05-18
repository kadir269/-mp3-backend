from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import yt_dlp, httpx, os, uuid, threading, time

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DOWNLOAD_DIR = "/tmp/dl"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def auto_delete(path, delay=300):
    def _d():
        time.sleep(delay)
        try: os.remove(path)
        except: pass
    threading.Thread(target=_d, daemon=True).start()

# yt-dlp ayarları — bot korumasını geçmek için
def get_opts(out_template=None):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["ios", "web_creator"],
            }
        },
        "http_headers": {
            "User-Agent": "com.google.ios.youtube/19.29.1 (iPhone16,2; U; CPU iOS 17_5 like Mac OS X)",
        },
    }
    if out_template:
        opts["outtmpl"] = out_template
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    return opts

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/info")
async def info(data: dict):
    url = data.get("url","").strip()
    if not url: raise HTTPException(400, "URL boş")
    try:
        with yt_dlp.YoutubeDL(get_opts()) as ydl:
            i = ydl.extract_info(url, download=False)
            thumb = i.get("thumbnail","")
            return {
                "title": i.get("title","?"),
                "thumbnail": thumb,
                "duration": i.get("duration", 0),
                "uploader": i.get("uploader","?"),
            }
    except Exception as e:
        raise HTTPException(400, str(e))

@app.post("/download")
async def download(data: dict):
    url = data.get("url","").strip()
    if not url: raise HTTPException(400, "URL boş")

    fid = str(uuid.uuid4())
    out = os.path.join(DOWNLOAD_DIR, f"{fid}.%(ext)s")
    mp3 = os.path.join(DOWNLOAD_DIR, f"{fid}.mp3")

    try:
        with yt_dlp.YoutubeDL(get_opts(out)) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title","muzik")
    except Exception as e:
        raise HTTPException(500, str(e))

    if not os.path.exists(mp3):
        raise HTTPException(500, "MP3 oluşturulamadı")

    auto_delete(mp3)
    safe = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:80]

    def gen():
        with open(mp3,"rb") as f:
            while chunk := f.read(8192): yield chunk

    return StreamingResponse(gen(), media_type="audio/mpeg",
        headers={
            "Content-Disposition": f'attachment; filename="{safe}.mp3"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        })
