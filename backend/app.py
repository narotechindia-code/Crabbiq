from __future__ import annotations

import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yt_dlp
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, HttpUrl

APP_NAME = "Crabbiq API"
DOWNLOAD_DIR = Path(os.getenv("CRABBIQ_DOWNLOAD_DIR", "/tmp/crabbiq-downloads")).resolve()
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_ACTIVE = max(1, int(os.getenv("CRABBIQ_MAX_ACTIVE", "2")))
MAX_URL_LENGTH = 4096
ALLOWED_SCHEMES = {"http", "https"}
_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()
_semaphore = threading.BoundedSemaphore(MAX_ACTIVE)

app = FastAPI(title=APP_NAME, version="1.0.0", docs_url="/docs", redoc_url="/redoc")
cors = [x.strip() for x in os.getenv("CRABBIQ_CORS", "http://localhost:3000,http://localhost:5173").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=cors or ["*"], allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["*"])

class InspectRequest(BaseModel):
    url: HttpUrl
    cookies_from_browser: str | None = Field(default=None, max_length=64)

class DownloadRequest(BaseModel):
    url: HttpUrl
    mode: str = Field(default="video", pattern="^(video|audio|image|auto)$")
    quality: str = Field(default="best", pattern="^(best|2160p|1440p|1080p|720p|480p|audio)$")
    audio_format: str = Field(default="mp3", pattern="^(mp3|m4a|wav|flac|opus)$")
    cookies_from_browser: str | None = Field(default=None, max_length=64)

def validate_url(value: str) -> str:
    if len(value) > MAX_URL_LENGTH: raise HTTPException(status_code=413, detail="URL is too long")
    parsed = urlparse(value)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES or not parsed.netloc: raise HTTPException(status_code=400, detail="Only absolute HTTP(S) URLs are supported")
    hostname = (parsed.hostname or "").lower().rstrip(".")
    blocked = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "169.254.169.254"}
    if hostname in blocked or hostname.endswith(".localhost"): raise HTTPException(status_code=400, detail="Local destinations are not accepted")
    return value

def extractor_options(*, cookie_browser: str | None = None, download: bool = False, outtmpl: str | None = None) -> dict[str, Any]:
    opts: dict[str, Any] = {"quiet": True, "no_warnings": True, "noplaylist": True, "socket_timeout": 20, "retries": 3, "fragment_retries": 3, "concurrent_fragment_downloads": 4, "restrictfilenames": True, "windowsfilenames": True, "nocheckcertificate": False, "cachedir": False, "skip_download": not download}
    if outtmpl: opts["outtmpl"] = outtmpl
    if cookie_browser: opts["cookiesfrombrowser"] = (cookie_browser,)
    return opts

def pick_format(mode: str, quality: str, audio_format: str) -> tuple[str, dict[str, Any]]:
    if mode == "audio" or quality == "audio":
        return "bestaudio/best", {"postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": audio_format, "preferredquality": "320"}]}
    if mode == "image": return "best", {"writethumbnail": True}
    height = {"2160p": 2160, "1440p": 1440, "1080p": 1080, "720p": 720, "480p": 480}.get(quality)
    fmt = f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best" if height else "bestvideo+bestaudio/best"
    return fmt, {"merge_output_format": "mp4"}

def safe_filename(name: str) -> str:
    name = re.sub(r"[\x00-\x1f<>:\"/\\|?*]", "_", name).strip(" .")
    return (name or "crabbiq-file")[:180]

def set_job(job_id: str, **changes: Any) -> None:
    with _jobs_lock:
        if job_id in _jobs: _jobs[job_id].update(changes)

def run_download(job_id: str, payload: DownloadRequest, url: str) -> None:
    acquired = _semaphore.acquire(timeout=1)
    if not acquired: set_job(job_id, status="queued"); _semaphore.acquire()
    try:
        set_job(job_id, status="downloading", progress=0)
        fmt, extra = pick_format(payload.mode, payload.quality, payload.audio_format)
        job_dir = DOWNLOAD_DIR / job_id; job_dir.mkdir(parents=True, exist_ok=True)
        outtmpl = str(job_dir / "%(title).180s [%(id)s].%(ext)s")
        def progress_hook(data: dict[str, Any]) -> None:
            if data.get("status") == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate"); done = data.get("downloaded_bytes", 0)
                set_job(job_id, progress=round((done / total) * 100, 1) if total else None, speed=data.get("speed"), eta=data.get("eta"))
            elif data.get("status") == "finished": set_job(job_id, progress=100)
        opts = extractor_options(cookie_browser=payload.cookies_from_browser, download=True, outtmpl=outtmpl); opts.update(extra); opts["format"] = fmt; opts["progress_hooks"] = [progress_hook]; opts["postprocessor_args"] = {"merger": ["-movflags", "+faststart"]}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            paths = [item.get("filepath") for item in (info.get("requested_downloads") or []) if item.get("filepath")]
            if not paths: paths = [ydl.prepare_filename(info)]
            existing = [Path(p) for p in paths if Path(p).exists()]
            if not existing: existing = [p for p in job_dir.iterdir() if p.is_file()]
            if not existing: raise RuntimeError("Download completed without a produced file")
            primary = existing[0]
            set_job(job_id, status="completed", progress=100, filename=primary.name, path=str(primary), title=info.get("title"), extractor=info.get("extractor"))
    except Exception as exc:
        set_job(job_id, status="failed", error=str(exc)[:1000])
    finally: _semaphore.release()

@app.get("/health")
def health() -> dict[str, Any]: return {"ok": True, "service": APP_NAME, "active_limit": MAX_ACTIVE}

@app.post("/api/inspect")
def inspect(payload: InspectRequest) -> dict[str, Any]:
    url = validate_url(str(payload.url))
    try:
        with yt_dlp.YoutubeDL(extractor_options(cookie_browser=payload.cookies_from_browser)) as ydl: info = ydl.extract_info(url, download=False)
        formats = [{"format_id":f.get("format_id"),"ext":f.get("ext"),"height":f.get("height"),"width":f.get("width"),"fps":f.get("fps"),"tbr":f.get("tbr"),"acodec":f.get("acodec"),"vcodec":f.get("vcodec"),"filesize":f.get("filesize") or f.get("filesize_approx"),"protocol":f.get("protocol")} for f in (info.get("formats") or [])]
        return {"ok":True,"extractor":info.get("extractor"),"title":info.get("title"),"duration":info.get("duration"),"thumbnail":info.get("thumbnail"),"uploader":info.get("uploader"),"webpage_url":info.get("webpage_url"),"is_playlist":bool(info.get("_type")=="playlist"),"formats":formats}
    except Exception as exc: raise HTTPException(status_code=422, detail={"message":"Unable to resolve this URL","reason":str(exc)[:1000]}) from exc

@app.post("/api/download", status_code=202)
def start_download(payload: DownloadRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    url = validate_url(str(payload.url)); job_id = uuid.uuid4().hex
    with _jobs_lock: _jobs[job_id] = {"id":job_id,"status":"queued","progress":0,"created_at":time.time()}
    background_tasks.add_task(run_download, job_id, payload, url)
    return {"ok":True,"job_id":job_id,"status":"queued"}

@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict[str, Any]:
    with _jobs_lock: job = _jobs.get(job_id)
    if not job: raise HTTPException(status_code=404, detail="Job not found")
    safe = {k:v for k,v in job.items() if k != "path"}
    if job.get("status") == "completed": safe["download_url"] = f"/api/jobs/{job_id}/file"
    return safe

@app.get("/api/jobs/{job_id}/file")
def download_file(job_id: str) -> FileResponse:
    with _jobs_lock: job = _jobs.get(job_id)
    if not job or job.get("status") != "completed": raise HTTPException(status_code=404, detail="Completed file not found")
    path = Path(job["path"]).resolve()
    if DOWNLOAD_DIR not in path.parents: raise HTTPException(status_code=500, detail="Invalid file location")
    if not path.is_file(): raise HTTPException(status_code=404, detail="File no longer exists")
    return FileResponse(path=str(path), filename=safe_filename(path.name), media_type="application/octet-stream")
