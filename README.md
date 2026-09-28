# Détoure

A small self-hosted service that removes image backgrounds, built on [rembg](https://github.com/danielgatis/rembg) and FastAPI. Images are processed on your server and are never stored.

## Features

- Drag and drop, file picker, or paste (Ctrl/Cmd+V) an image: JPEG, PNG, WebP or HEIC (iPhone photos)
- Choice of segmentation model
- Optional alpha matting ("Fine edges") for finer hair and fur edges
- Before/after comparison slider
- Download the result as a transparent PNG
- Optional HTTP Basic authentication

## Run locally

```bash
docker build -t detoure .
docker run -p 8000:8000 detoure
```

Then open http://localhost:8000.

> **Apple Silicon:** if `DOCKER_DEFAULT_PLATFORM=linux/amd64` is set in your shell, add `--platform linux/arm64` to both `build` and `run`. Otherwise the image runs under emulation and processing is much slower.

## Deploy on Coolify

1. **New Resource → Public Repository** (or Private Repository), select this repo and the `main` branch.
2. **Build Pack: Dockerfile** (the `Dockerfile` is at the repo root).
3. **Ports Exposes: `8000`**.
4. Add a domain, then **Deploy**.

The health check (`/health`) is declared in the Dockerfile and picked up by Coolify automatically.

### Environment variables (all optional)

| Variable | Default | Description |
| --- | --- | --- |
| `APP_USER` / `APP_PASSWORD` | empty | Enables HTTP Basic authentication when `APP_PASSWORD` is set. **Recommended** if the URL is public. |
| `MODELE_DEFAUT` | `isnet-general-use` | Model selected by default. |
| `TAILLE_MAX_MO` | `25` | Maximum upload size, in MB. |
| `COTE_MAX_PX` | `4096` | Larger images are downscaled before processing. |
| `TRAVAUX_SIMULTANES` | `1` | Number of images processed in parallel (each model uses RAM). |

### Persistent storage (optional)

Only `isnet-general-use` is bundled in the image. Other models are downloaded to `/models` on first use (up to ~1 GB for `birefnet-general`) and lost on every redeploy. To keep them, add a **persistent volume** mounted at `/models` in Coolify.

### Resources

Plan for at least **2 GB of RAM** (more if you use `birefnet-general`). Inference runs on CPU.

## Models

| ID | Label in the UI | Notes |
| --- | --- | --- |
| `isnet-general-use` | General purpose | Good quality/speed trade-off (default, bundled) |
| `u2net` | Fast | Lightweight, less precise edges |
| `u2net_human_seg` | Portraits | Tuned for people |
| `birefnet-general` | High quality | Very fine edges, slow |

The list lives in `MODELES` in `app/main.py`. Any [rembg session name](https://github.com/danielgatis/rembg#models) can be added there.

## API

- `GET /api/modeles`: available models and the default one.
- `POST /api/detourer` (multipart): `image` (file), `modele` (optional), `contours_fins` (`true`/`false`). Returns a transparent PNG.
- `GET /health`: service status.

## Project structure

```
app/
  main.py           FastAPI app and rembg processing
  static/index.html Single-page web UI
Dockerfile
requirements.txt
```
