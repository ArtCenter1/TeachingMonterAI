# 🐳 Running Teaching Monster AI with Docker

No more keeping terminal windows open! Docker runs everything in the background.

## One-Time Setup

### 1. Get your ngrok Auth Token
1. Go to https://dashboard.ngrok.com/get-started/your-authtoken
2. Copy your token
3. Open `.env` and replace `your_ngrok_authtoken_here` with your token

Your `.env` should have:
```
NGROK_AUTHTOKEN=2abc123xyz...
```

### 2. (Optional) Get a free static ngrok domain
Without this, your public URL changes every restart.

1. Go to https://dashboard.ngrok.com/cloud-edge/domains
2. Click "New Domain" → get a free static URL like `teaching-monster.ngrok-free.app`  
3. Uncomment and set in `.env`:
```
NGROK_DOMAIN=teaching-monster.ngrok-free.app
```

---

## Daily Usage

### ▶️ Start everything (runs in background)
```bash
docker compose up -d --build
```

### 🔎 Find your public URL
```bash
# Option 1: ngrok web UI
open http://localhost:4040

# Option 2: curl the API
curl http://localhost:4040/api/tunnels
```

### 📋 View logs
```bash
# All services
docker compose logs -f

# Just the app
docker compose logs -f app

# Just ngrok
docker compose logs -f ngrok
```

### ⏹️ Stop everything
```bash
docker compose down
```

### 🔄 Restart after code changes
```bash
docker compose up -d --build
```

---

## Architecture

```
Internet
   │
   ▼
ngrok (container) ← free HTTPS tunnel
   │  https://your-domain.ngrok-free.app
   │
   ▼
app (container) :8000
   │  FastAPI + all pipeline modules
   │  FFmpeg installed inside container
   │
   ▼
./temp/ ← generated videos on your host machine
```

## Ports

| Port | Service |
|------|---------|
| `8000` | FastAPI app (local only) |
| `4040` | ngrok web UI (to get your public URL) |

## Output Files

Generated videos appear in `./temp/output/` on your machine (Docker mounts this folder).
