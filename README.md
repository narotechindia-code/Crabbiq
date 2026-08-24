# Crabbiq

Premium all-in-one media downloader by Narotech India.

## Architecture

- Static premium frontend: GitHub Pages
- API: FastAPI + yt-dlp
- Media processing: FFmpeg inside backend container
- Persistent browser workspace: localStorage
- PWA shell with offline UI caching

## Frontend

The GitHub Pages workflow deploys the repository root. After Pages is enabled for the repository, the expected public URL is:

`https://narotechindia-code.github.io/Crabbiq/`

Open **Profile** in Crabbiq and set the deployed API URL. The API endpoint is intentionally configurable so the static frontend can be hosted independently from the media-processing service.

## Backend

Build locally:

```bash
cd backend
docker build -t crabbiq-api .
docker run --rm -p 8000:8000 -e CRABBIQ_CORS=http://localhost:8000 crabbiq-api
```

Health check: `GET /health`

Inspection: `POST /api/inspect` with `{ "url": "https://..." }`

Download: `POST /api/download` with URL, mode, quality and audio format.

Job status: `GET /api/jobs/{job_id}`

File: `GET /api/jobs/{job_id}/file`

A Render deployment manifest is included as `render.yaml`.

## Resolver coverage

Crabbiq uses yt-dlp's maintained extractor ecosystem plus generic extraction/direct-media paths and a documented strategy for file hosts such as Way2Share and Keep2Share. Actual support is determined by successful extraction at runtime; private, expired, CAPTCHA-protected, DRM-protected or otherwise inaccessible resources return an error rather than a fake result.

## Production security

The backend validates HTTP(S) URLs, blocks obvious local loopback destinations, sanitizes filenames, limits concurrent work, applies timeouts/retries and keeps downloaded files under a controlled directory. Deploy behind HTTPS and set `CRABBIQ_CORS` to the exact public frontend origin.

Do not use Crabbiq to bypass DRM, paywalls, CAPTCHAs, authentication controls or other access restrictions. Use only content you are authorized to access and download.
