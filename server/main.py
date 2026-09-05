#!/usr/bin/env python3
"""Hermes×Obsidian Phase-4 API: Hermes-first organize + free-tier quota stub."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

ROOT = Path(__file__).resolve().parent.parent
ORGANIZE_SCRIPT = ROOT / "organize_vault.py"
HERMES_SCRIPT = ROOT / "run_hermes_organize.sh"
JOBS_DIR = Path(__file__).resolve().parent / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)
QUOTA_FILE = JOBS_DIR / "quota.json"
HERMES_ENV_FILE = Path.home() / ".hermes" / ".env"

# Free tier: 5 organizes per calendar day (Asia/Shanghai)
QUOTA_LIMIT = 5
QUOTA_TZ = ZoneInfo("Asia/Shanghai")
HERMES_TIMEOUT_SEC = int(os.environ.get("HERMES_TIMEOUT_SEC", "240"))  # 180–300s band
SCRIPT_TIMEOUT_SEC = 120

API_KEY_NAMES = (
    "OPENROUTER_API_KEY",
    "DEEPSEEK_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "NOUS_API_KEY",
    "GLM_API_KEY",
    "KIMI_API_KEY",
    "FIREWORKS_API_KEY",
)

# In-memory job registry (demo-scale; restart clears)
JOBS: dict[str, dict] = {}

app = FastAPI(title="Hermes×Obsidian API", version="0.4.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "hermes-obsidian",
        "phase": 4,
        "version": "0.4.0",
    }


def _today_key() -> str:
    return datetime.now(QUOTA_TZ).strftime("%Y-%m-%d")


def _client_id_from_header(x_client_id: Optional[str]) -> str:
    raw = (x_client_id or "").strip()
    if not raw:
        return "anonymous"
    # Keep storage keys safe / short
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "", raw)[:64]
    return cleaned or "anonymous"


def _load_quota() -> dict:
    if not QUOTA_FILE.is_file():
        return {}
    try:
        data = json.loads(QUOTA_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_quota(data: dict) -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = QUOTA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(QUOTA_FILE)


def _quota_snapshot(client_id: str) -> dict:
    today = _today_key()
    store = _load_quota()
    day = store.get(today) if isinstance(store.get(today), dict) else {}
    used = int(day.get(client_id, 0) or 0)
    remaining = max(0, QUOTA_LIMIT - used)
    return {
        "client_id": client_id,
        "used": used,
        "limit": QUOTA_LIMIT,
        "remaining": remaining,
        "day": today,
        "tz": "Asia/Shanghai",
    }


def _check_and_consume_quota(client_id: str) -> dict:
    """Raise 429 if over free limit; otherwise increment and return snapshot."""
    today = _today_key()
    store = _load_quota()
    # Drop old days to keep file small
    store = {k: v for k, v in store.items() if k == today and isinstance(v, dict)}
    day = store.setdefault(today, {})
    used = int(day.get(client_id, 0) or 0)
    if used >= QUOTA_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"今日免费整理次数已用完（上限 {QUOTA_LIMIT} 次/天，时区 Asia/Shanghai）。请明天再试。",
        )
    day[client_id] = used + 1
    store[today] = day
    _save_quota(store)
    return _quota_snapshot(client_id)


@app.get("/api/quota")
def get_quota(x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id")):
    client_id = _client_id_from_header(x_client_id)
    snap = _quota_snapshot(client_id)
    return {
        "client_id": snap["client_id"],
        "used": snap["used"],
        "limit": snap["limit"],
        "remaining": snap["remaining"],
    }


def _has_model_api_key() -> bool:
    """True if a usable model API key exists in process env or ~/.hermes/.env.
    Never returns or logs key values.
    """
    for name in API_KEY_NAMES:
        val = os.environ.get(name, "").strip()
        if val and "PASTE" not in val.upper():
            return True
    if not HERMES_ENV_FILE.is_file():
        return False
    try:
        text = HERMES_ENV_FILE.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key in API_KEY_NAMES and val and "PASTE" not in val.upper():
            return True
    return False


def _safe_extract_zip(zip_path: Path, dest: Path) -> None:
    """Extract zip while blocking path traversal."""
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            target = (dest / info.filename).resolve()
            if not str(target).startswith(str(dest.resolve())):
                raise HTTPException(status_code=400, detail="Invalid zip entry path")
        zf.extractall(dest)


def _collect_upload_to_input(files: list[UploadFile], work: Path) -> Path:
    """Save uploads into work/input/; unzip .zip archives into input."""
    input_dir = work / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    for uf in files:
        name = Path(uf.filename or "upload.bin").name
        raw = work / "uploads" / name
        raw.parent.mkdir(parents=True, exist_ok=True)
        with raw.open("wb") as out:
            shutil.copyfileobj(uf.file, out)

        if name.lower().endswith(".zip"):
            extract_to = input_dir / raw.stem
            extract_to.mkdir(parents=True, exist_ok=True)
            try:
                _safe_extract_zip(raw, extract_to)
            except zipfile.BadZipFile as e:
                raise HTTPException(status_code=400, detail=f"Bad zip: {name}") from e
            # If zip contained a single top-level folder, flatten one level for convenience
            children = [p for p in extract_to.iterdir()]
            if len(children) == 1 and children[0].is_dir():
                for child in children[0].iterdir():
                    dest = extract_to / child.name
                    if not dest.exists():
                        shutil.move(str(child), str(dest))
                try:
                    children[0].rmdir()
                except OSError:
                    pass
        else:
            shutil.copy2(raw, input_dir / name)

    # If only one extracted zip folder and no loose files, use that as input root
    entries = list(input_dir.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return input_dir


def _run_script_organizer(input_dir: Path, output_dir: Path) -> dict:
    """Offline deterministic fallback: organize_vault.py."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "python3",
        str(ORGANIZE_SCRIPT),
        "--input",
        str(input_dir),
        "--output",
        str(output_dir),
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=SCRIPT_TIMEOUT_SEC,
        cwd=str(ROOT),
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "organizer failed")[-2000:]
        raise HTTPException(status_code=500, detail=f"Organizer failed: {err}")
    home = output_dir / "Home.md"
    if not home.is_file():
        raise HTTPException(status_code=500, detail="Organizer did not produce Home.md")
    return {
        "engine": "script",
        "note": "Offline deterministic organizer (organize_vault.py).",
        "stdout_tail": (proc.stdout or "")[-500:],
    }


def _run_hermes_organizer(input_dir: Path, output_dir: Path) -> dict:
    """Call run_hermes_organize.sh with job-specific INPUT_DIR / OUTPUT_DIR."""
    output_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["INPUT_DIR"] = str(input_dir)
    env["OUTPUT_DIR"] = str(output_dir)
    env["OBSIDIAN_VAULT_PATH"] = str(output_dir)
    # Soft budget slightly under process timeout
    env.setdefault("HERMES_RUN_BUDGET", str(max(60, HERMES_TIMEOUT_SEC - 30)))

    proc = subprocess.run(
        ["bash", str(HERMES_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=HERMES_TIMEOUT_SEC,
        cwd=str(ROOT),
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"hermes exit {proc.returncode}: {(proc.stderr or proc.stdout or '')[-800:]}"
        )
    home = output_dir / "Home.md"
    if not home.is_file():
        # Hermes may have written something but not Home.md — treat as soft failure
        raise RuntimeError("Hermes finished but Home.md missing")
    return {
        "engine": "hermes",
        "note": "Hermes agent via run_hermes_organize.sh",
        "stdout_tail": (proc.stdout or "")[-500:],
    }


def _run_organizer(input_dir: Path, output_dir: Path) -> dict:
    """
    Prefer Hermes when API key + script exist; on any failure fall back to script.
    Returns engine: "hermes" | "script". Never logs API keys.
    """
    try_hermes = (
        HERMES_SCRIPT.is_file()
        and os.access(HERMES_SCRIPT, os.X_OK)
        and _has_model_api_key()
    )
    if try_hermes:
        try:
            return _run_hermes_organizer(input_dir, output_dir)
        except Exception as exc:
            # Fall back; keep message free of secrets
            print(f"[organize] Hermes unavailable, falling back to script: {type(exc).__name__}")
            # Clean partial output so script starts fresh
            if output_dir.exists():
                shutil.rmtree(output_dir, ignore_errors=True)
            meta = _run_script_organizer(input_dir, output_dir)
            meta["note"] = (
                f"Hermes failed ({type(exc).__name__}); used organize_vault.py fallback."
            )
            meta["hermes_attempted"] = True
            return meta
    return _run_script_organizer(input_dir, output_dir)


def _zip_vault(vault_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in vault_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(vault_dir).as_posix())


@app.post("/api/organize")
async def organize(
    files: list[UploadFile] = File(...),
    x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"),
):
    """
    Accept multipart .zip of notes and/or multiple files.
    Runs organizer (Hermes-first), zips vault, returns job_id for download.
    """
    client_id = _client_id_from_header(x_client_id)
    quota = _check_and_consume_quota(client_id)

    job_id = uuid.uuid4().hex
    work = Path(tempfile.mkdtemp(prefix=f"job-{job_id}-", dir=str(JOBS_DIR)))
    try:
        input_dir = _collect_upload_to_input(files, work)
        # Ensure we have at least one file under input
        file_count = sum(1 for p in input_dir.rglob("*") if p.is_file())
        if file_count == 0:
            raise HTTPException(status_code=400, detail="Upload contained no files")

        output_dir = work / "vault"
        meta = _run_organizer(input_dir, output_dir)

        zip_path = work / "vault.zip"
        _zip_vault(output_dir, zip_path)

        JOBS[job_id] = {
            "job_id": job_id,
            "status": "done",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "zip_path": str(zip_path),
            "work_dir": str(work),
            "engine": meta["engine"],
            "file_count": file_count,
            "client_id": client_id,
        }
        return JSONResponse(
            {
                "job_id": job_id,
                "status": "done",
                "download_url": f"/api/download/{job_id}",
                "engine": meta["engine"],
                "file_count": file_count,
                "quota": {
                    "used": quota["used"],
                    "limit": quota["limit"],
                    "remaining": quota["remaining"],
                },
            }
        )
    except HTTPException:
        shutil.rmtree(work, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(work, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Organize error: {type(e).__name__}") from e


@app.get("/api/download/{job_id}")
def download(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown or expired job_id")
    zip_path = Path(job["zip_path"])
    if not zip_path.is_file():
        raise HTTPException(status_code=404, detail="Vault zip missing")
    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename=f"obsidian-vault-{job_id[:8]}.zip",
    )


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown or expired job_id")
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "created_at": job["created_at"],
        "engine": job.get("engine"),
        "file_count": job.get("file_count"),
        "download_url": f"/api/download/{job_id}",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8787, reload=False)
