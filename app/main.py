"""Détoure : petit service auto-hébergé pour enlever le fond des images."""

import asyncio
import io
import os
import secrets
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener
from rembg import new_session, remove

register_heif_opener()  # support des photos iPhone (HEIC)

# --- Configuration (variables d'environnement, modifiables dans Coolify) ---
MODELE_DEFAUT = os.getenv("MODELE_DEFAUT", "isnet-general-use")
TAILLE_MAX_MO = int(os.getenv("TAILLE_MAX_MO", "25"))
COTE_MAX_PX = int(os.getenv("COTE_MAX_PX", "2048"))
TRAVAUX_SIMULTANES = int(os.getenv("TRAVAUX_SIMULTANES", "1"))
APP_USER = os.getenv("APP_USER", "")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")

MODELES = {
    "isnet-general-use": "General purpose : good balance of quality and speed",
    "u2net": "Fast : lightweight, less precise edges",
    "u2net_human_seg": "Portraits : tuned for people",
    "birefnet-general": "High quality : very fine edges, slow (≈ 1 GB download on first use)",
}
if MODELE_DEFAUT not in MODELES:
    MODELE_DEFAUT = "isnet-general-use"

STATIC = Path(__file__).parent / "static"

# --- Sessions de modèles : chargées une fois puis gardées en mémoire ---
_sessions: dict = {}
_verrou_sessions = threading.Lock()


def obtenir_session(nom: str):
    with _verrou_sessions:
        if nom not in _sessions:
            _sessions[nom] = new_session(nom)
        return _sessions[nom]


def detourer(donnees: bytes, modele: str, contours_fins: bool) -> bytes:
    image = Image.open(io.BytesIO(donnees))
    image = ImageOps.exif_transpose(image)  # respecte l'orientation du téléphone
    image.thumbnail((COTE_MAX_PX, COTE_MAX_PX))
    image = image.convert("RGB")

    resultat = remove(
        image,
        session=obtenir_session(modele),
        alpha_matting=contours_fins,
        post_process_mask=True,
    )
    tampon = io.BytesIO()
    resultat.save(tampon, format="PNG")
    return tampon.getvalue()


# --- Authentification optionnelle (activée si APP_PASSWORD est défini) ---
_basic = HTTPBasic(auto_error=False)


def verifier_acces(identifiants: HTTPBasicCredentials | None = Depends(_basic)):
    if not APP_PASSWORD:
        return
    ok = identifiants is not None and secrets.compare_digest(
        identifiants.username.encode(), APP_USER.encode()
    ) and secrets.compare_digest(identifiants.password.encode(), APP_PASSWORD.encode())
    if not ok:
        raise HTTPException(
            status_code=401,
            detail="Credentials required",
            headers={"WWW-Authenticate": 'Basic realm="Detoure"'},
        )


app = FastAPI(title="Détoure", docs_url=None, redoc_url=None)
protege = APIRouter(dependencies=[Depends(verifier_acces)])
_file_attente = asyncio.Semaphore(TRAVAUX_SIMULTANES)


@app.get("/health")
def health():
    return {"statut": "ok"}


@protege.get("/")
def accueil():
    return FileResponse(STATIC / "index.html")


@protege.get("/api/modeles")
def lister_modeles():
    return {
        "defaut": MODELE_DEFAUT,
        "modeles": [{"id": k, "description": v} for k, v in MODELES.items()],
        "taille_max_mo": TAILLE_MAX_MO,
    }


@protege.post("/api/detourer")
async def api_detourer(
    image: UploadFile = File(...),
    modele: str = Form(MODELE_DEFAUT),
    contours_fins: bool = Form(False),
):
    if modele not in MODELES:
        raise HTTPException(400, f"Unknown model: {modele}")

    limite = TAILLE_MAX_MO * 1024 * 1024
    donnees = await image.read(limite + 1)
    if len(donnees) > limite:
        raise HTTPException(413, f"Image too large (maximum {TAILLE_MAX_MO} MB).")
    if not donnees:
        raise HTTPException(400, "Empty file.")

    async with _file_attente:
        try:
            png = await run_in_threadpool(detourer, donnees, modele, contours_fins)
        except UnidentifiedImageError:
            raise HTTPException(415, "Unrecognized format. Use a JPEG, PNG, WebP or HEIC image.")

    return Response(content=png, media_type="image/png")


app.include_router(protege)
