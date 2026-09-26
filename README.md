# Reel2Short

Convert Instagram Reels to YouTube Shorts — local-first web application.

## Stage 1 — Local Foundation

### Requirements

- Python 3.11+
- Node.js 20+
- ffprobe (optional — for video metadata detection; download ffmpeg from [ffmpeg.org](https://ffmpeg.org))
- An Instagram Business/Creator account with a valid access token

### Setup

#### 1. Clone / open the project

```powershell
cd C:\Users\venka\Documents\Reel2Short
```

#### 2. Configure environment

Copy `.env.example` to `.env` (or edit the existing `.env`):

```
INSTAGRAM_ACCESS_TOKEN=<your_long-lived_token>
FFPROBE_PATH=ffprobe          # or full path e.g. C:\ffmpeg\bin\ffprobe.exe
```

#### 3. Backend

```powershell
# Create venv (already done if you ran setup)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install -r backend\requirements.txt

# Start the server
cd backend
python run.py
```

Backend runs at: http://127.0.0.1:8000  
API docs: http://127.0.0.1:8000/docs

#### 4. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend runs at: http://localhost:5173

---

### Testing Stage 1

#### Health check
```
GET http://localhost:8000/api/health
```

#### Instagram Reels
```
GET http://localhost:8000/api/instagram/reels
```

#### Reel status
```
GET http://localhost:8000/api/instagram/reels/{media_id}/status
```

#### Download a Reel (multipart form)
```
POST http://localhost:8000/api/videos/download
Fields: media_id, media_url, caption (optional), permalink (optional)
```

#### Manual upload
```
POST http://localhost:8000/api/videos/upload
Fields: file (MP4/MOV), source_media_id (optional)
```

#### List videos
```
GET http://localhost:8000/api/videos
```

---

### ffprobe (optional)

Without ffprobe, width/height/duration will show as `null`. The rest of the app works fine.

To install:
1. Download [FFmpeg](https://www.gyan.dev/ffmpeg/builds/) (Windows builds)
2. Extract and add `bin/` to your PATH, or set `FFPROBE_PATH=C:\ffmpeg\bin\ffprobe.exe` in `.env`

---

### Storage

Videos are stored in:

```
storage/
  downloads/   ← Instagram downloads
  uploads/     ← manual uploads
  converted/   ← (Stage 2+)
  temp/        ← cleaned up after download
```

### Project Structure

```
Reel2Short/
├── backend/
│   ├── app/
│   │   ├── main.py          FastAPI app
│   │   ├── config.py        Settings from .env
│   │   ├── database.py      SQLite / SQLAlchemy
│   │   ├── api/             Routers
│   │   ├── models/          ORM models
│   │   ├── schemas/         Pydantic schemas
│   │   └── services/        Business logic
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   └── src/
│       ├── pages/           Dashboard, Reels, Download, Upload, Videos
│       ├── components/      Sidebar, ErrorAlert, Spinner, etc.
│       ├── services/        API client
│       └── types/           TypeScript types
├── storage/
├── .env
└── .env.example
```

