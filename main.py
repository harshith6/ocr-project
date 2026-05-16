from __future__ import annotations

import os
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any


def _apply_low_memory_env_defaults() -> None:
    """Cap BLAS/OpenMP threads to reduce RAM spikes on small EC2 instances (OOM killer -> Killed)."""
    for key in (
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        if key not in os.environ:
            os.environ[key] = "1"


_apply_low_memory_env_defaults()

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "static"
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/bmp"}

app = FastAPI(title="Simple OCR Extractor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _paddleocr_model_dir() -> str:
    """Where PaddleOCR stores downloaded weights (set PADDLEOCR_MODEL_DIR on small/persistent disks)."""
    raw = os.environ.get("PADDLEOCR_MODEL_DIR", str(BASE_DIR / ".paddleocr"))
    path = Path(raw)
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return default


@lru_cache(maxsize=1)
def get_ocr_engine() -> Any:
    # Lazy import: keeps `/` and static assets working without loading Paddle until first OCR.
    from paddleocr import PaddleOCR

    use_angle_cls = _env_flag("PADDLEOCR_USE_ANGLE_CLS", True)
    use_mkldnn = _env_flag("PADDLEOCR_USE_MKLDNN", False)

    return PaddleOCR(
        use_angle_cls=use_angle_cls,
        lang="en",
        show_log=False,
        use_mkldnn=use_mkldnn,
        model_storage_directory=_paddleocr_model_dir(),
    )


def parse_ocr_result(result: list[Any]) -> tuple[str, list[dict[str, Any]]]:
    lines: list[dict[str, Any]] = []

    for page in result or []:
        if not page:
            continue

        for item in page:
            if len(item) < 2:
                continue

            box = item[0]
            text_info = item[1]
            text = text_info[0] if text_info else ""
            confidence = float(text_info[1]) if len(text_info) > 1 else None

            if text:
                lines.append(
                    {
                        "text": text,
                        "confidence": confidence,
                        "box": box,
                    }
                )

    extracted_text = "\n".join(line["text"] for line in lines)
    return extracted_text, lines


@app.post("/api/ocr")
async def extract_text(file: UploadFile = File(...)) -> dict[str, Any]:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Please upload a JPG, PNG, WEBP, or BMP image.",
        )

    suffix = Path(file.filename or "image").suffix or ".png"
    temp_path = ""

    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded image is empty.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(contents)
            temp_path = temp_file.name

        use_cls = _env_flag("PADDLEOCR_USE_ANGLE_CLS", True)
        result = get_ocr_engine().ocr(temp_path, cls=use_cls)
        text, lines = parse_ocr_result(result)

        return {
            "text": text,
            "lines": lines,
            "line_count": len(lines),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"OCR failed: {exc}") from exc
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    index_file = FRONTEND_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend not found.")
    return FileResponse(index_file)
