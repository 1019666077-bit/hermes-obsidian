#!/usr/bin/env python3
"""Hermes×Obsidian Phase-3 API: upload messy notes → organized Obsidian vault zip."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

ROOT = Path(__file__).resolve().parent.parent
ORGANIZE_SCRIPT = ROOT / "organize_vault.py"
JOBS_DIR = Path(__file__).resolve().parent / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)

# In-memory job registry (demo-scale; restart clears)
JOBS: dict[str, dict] = {}

app = FastAPI(title="Hermes×Obsidian API", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "hermes-obsidian", "phase": 3}


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


def _run_organizer(input_dir: Path, output_dir: Path) -> dict:
    """
    Reliable demo default: organize_vault.py --input/--output (no LLM).
    Hermes (run_hermes_organize.sh) can replace this later when API keys exist.
    """
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
        timeout=120,
        cwd=str(ROOT),
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "organizer failed")[-2000:]
        raise HTTPException(status_code=500, detail=f"Organizer failed: {err}")
    home = output_dir / "Home.md"
    if not home.is_file():
        raise HTTPException(status_code=500, detail="Organizer did not produce Home.md")
    return {
        "engine": "organize_vault.py",
        "note": "Offline deterministic organizer. Hermes can replace later via run_hermes_organize.sh.",
        "stdout_tail": (proc.stdout or "")[-500:],
    }


def _zip_vault(vault_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in vault_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(vault_dir).as_posix())


@app.post("/api/organize")
async def organize(files: list[UploadFile] = File(...)):
    """
    Accept multipart .zip of notes and/or multiple files.
    Runs organizer, zips vault, returns job_id for download.
    """
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
        }
        return JSONResponse(
            {
                "job_id": job_id,
                "status": "done",
                "download_url": f"/api/download/{job_id}",
                "engine": meta["engine"],
                "file_count": file_count,
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
