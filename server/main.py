#!/usr/bin/env python3
"""Hermes×Obsidian Phase-5 API: Docker-ready + WeChat login stub + organize."""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
ORGANIZE_SCRIPT = ROOT / "organize_vault.py"
HERMES_SCRIPT = ROOT / "run_hermes_organize.sh"
JOBS_DIR = Path(__file__).resolve().parent / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)
QUOTA_FILE = JOBS_DIR / "quota.json"
SESSIONS_FILE = JOBS_DIR / "sessions.json"
HERMES_ENV_FILE = Path.home() / ".hermes" / ".env"

# Free tier: configurable organizes per calendar day (Asia/Shanghai)
QUOTA_LIMIT = int(os.environ.get("FREE_QUOTA_LIMIT", os.environ.get("QUOTA_DAILY_LIMIT", "5")))
QUOTA_TZ = ZoneInfo("Asia/Shanghai")
QUOTA_UPGRADE_HINT = "开通会员可继续整理。当前为演示，暂无在线支付，请联系管理员手工开通。"
QUOTA_UPGRADE_CTA = "开通会员"
HERMES_TIMEOUT_SEC = int(os.environ.get("HERMES_TIMEOUT_SEC", "240"))  # 180–300s band
SCRIPT_TIMEOUT_SEC = 120
SESSION_DAYS = 7
ORGANIZE_ENGINE = (os.environ.get("ORGANIZE_ENGINE") or "auto").strip().lower()

WECHAT_APPID = (os.environ.get("WECHAT_APPID") or "").strip()
WECHAT_SECRET = (os.environ.get("WECHAT_SECRET") or "").strip()
WECHAT_LOGIN_READY = bool(WECHAT_APPID and WECHAT_SECRET)

# WeChat jscode2session errcode → 中文说明（不回传 secret）
WECHAT_ERR_HINTS = {
    40013: "AppID 无效，请核对 .env 的 WECHAT_APPID 是否与公众平台小程序 AppID 一致。",
    40125: "AppSecret 错误，请在公众平台重置并更新 .env 的 WECHAT_SECRET 后重启。",
    40029: "code 无效：可能已过期、已使用，或小程序 AppID 与服务器不一致。请重新 wx.login。",
    40163: "code 已使用，请重新 wx.login 获取新 code。",
    45011: "登录调用过于频繁，请稍后重试。",
    40226: "微信拒绝该用户登录（高风险标记）。",
}

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

app = FastAPI(title="Hermes×Obsidian API", version="0.5.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginBody(BaseModel):
    code: str = Field(..., min_length=1, description="wx.login code or any string in dev mode")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "hermes-obsidian",
        "phase": 5,
        "version": "0.5.0",
        "wechat_login": "live" if WECHAT_LOGIN_READY else "dev",
        "organize_engine": ORGANIZE_ENGINE,
    }


def _today_key() -> str:
    return datetime.now(QUOTA_TZ).strftime("%Y-%m-%d")


def _client_id_from_header(x_client_id: Optional[str]) -> str:
    raw = (x_client_id or "").strip()
    if not raw:
        return "anonymous"
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "", raw)[:64]
    return cleaned or "anonymous"


def _load_json_file(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_json_file(path: Path, data: dict) -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _load_quota() -> dict:
    return _load_json_file(QUOTA_FILE)


def _save_quota(data: dict) -> None:
    _save_json_file(QUOTA_FILE, data)


def _load_sessions() -> dict:
    return _load_json_file(SESSIONS_FILE)


def _save_sessions(data: dict) -> None:
    _save_json_file(SESSIONS_FILE, data)


def _purge_expired_sessions(store: dict) -> dict:
    now = datetime.now(timezone.utc)
    cleaned: dict = {}
    for token, meta in store.items():
        if not isinstance(meta, dict):
            continue
        exp = meta.get("expires_at")
        if not exp:
            continue
        try:
            expires = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
        except ValueError:
            continue
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires > now:
            cleaned[token] = meta
    return cleaned


def _issue_session(openid: str, mode: str) -> dict:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=SESSION_DAYS)
    store = _purge_expired_sessions(_load_sessions())
    store[token] = {
        "openid": openid,
        "mode": mode,
        "created_at": now.isoformat(),
        "expires_at": expires.isoformat(),
    }
    _save_sessions(store)
    return {
        "session_token": token,
        "openid": openid,
        "expires_at": expires.isoformat(),
        "mode": mode,
        "expires_in_sec": SESSION_DAYS * 24 * 3600,
    }


def _openid_from_bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    raw = authorization.strip()
    if not raw.lower().startswith("bearer "):
        return None
    token = raw[7:].strip()
    if not token:
        return None
    store = _purge_expired_sessions(_load_sessions())
    # Persist purge occasionally
    _save_sessions(store)
    meta = store.get(token)
    if not isinstance(meta, dict):
        return None
    openid = str(meta.get("openid") or "").strip()
    return openid or None


def _resolve_quota_key(
    authorization: Optional[str] = None,
    x_client_id: Optional[str] = None,
) -> dict:
    """Prefer openid from Bearer session; else X-Client-Id."""
    openid = _openid_from_bearer(authorization)
    if openid:
        return {
            "quota_key": f"oid:{openid}",
            "openid": openid,
            "client_id": _client_id_from_header(x_client_id),
            "auth": "bearer",
        }
    client_id = _client_id_from_header(x_client_id)
    return {
        "quota_key": client_id,
        "openid": None,
        "client_id": client_id,
        "auth": "client_id",
    }


def _quota_copy(remaining: int) -> dict:
    """User-facing free-trial / 开通 copy. Stub membership only — no payment."""
    exhausted = remaining <= 0
    if exhausted:
        hint = (
            f"今日 {QUOTA_LIMIT} 次免费额度已用完，明天 0 点（北京时间）恢复。"
            "也可开通会员继续整理。"
        )
    elif remaining == QUOTA_LIMIT:
        hint = f"免费试用：每天可整理 {QUOTA_LIMIT} 次。用完后第二天恢复，或开通会员。"
    else:
        hint = f"今日还可整理 {remaining} 次（共 {QUOTA_LIMIT} 次）。用完后第二天恢复，或开通会员。"
    return {
        "plan": "free",
        "plan_label": "免费试用",
        "hint": hint,
        "upgrade_cta": QUOTA_UPGRADE_CTA,
        "upgrade_hint": QUOTA_UPGRADE_HINT,
        "exhausted": exhausted,
    }


def _quota_public_fields(snap: dict) -> dict:
    copy = _quota_copy(snap["remaining"])
    return {
        "used": snap["used"],
        "limit": snap["limit"],
        "remaining": snap["remaining"],
        "day": snap["day"],
        "tz": snap["tz"],
        **copy,
    }


def _quota_snapshot(quota_key: str) -> dict:
    today = _today_key()
    store = _load_quota()
    day = store.get(today) if isinstance(store.get(today), dict) else {}
    used = int(day.get(quota_key, 0) or 0)
    remaining = max(0, QUOTA_LIMIT - used)
    return {
        "quota_key": quota_key,
        "used": used,
        "limit": QUOTA_LIMIT,
        "remaining": remaining,
        "day": today,
        "tz": "Asia/Shanghai",
    }


def _check_and_consume_quota(quota_key: str) -> dict:
    """Raise 429 if over free limit; otherwise increment and return snapshot."""
    today = _today_key()
    store = _load_quota()
    store = {k: v for k, v in store.items() if k == today and isinstance(v, dict)}
    day = store.setdefault(today, {})
    used = int(day.get(quota_key, 0) or 0)
    if used >= QUOTA_LIMIT:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "QUOTA_EXHAUSTED",
                "message": (
                    f"今日免费次数已用完（每天 {QUOTA_LIMIT} 次，按北京时间计算）。"
                    "明天 0 点自动恢复。"
                ),
                "upgrade_cta": QUOTA_UPGRADE_CTA,
                "upgrade_hint": QUOTA_UPGRADE_HINT,
                "limit": QUOTA_LIMIT,
                "used": used,
                "remaining": 0,
            },
        )
    day[quota_key] = used + 1
    store[today] = day
    _save_quota(store)
    return _quota_snapshot(quota_key)


def _wechat_jscode2session(code: str) -> dict:
    params = urllib.parse.urlencode(
        {
            "appid": WECHAT_APPID,
            "secret": WECHAT_SECRET,
            "js_code": code,
            "grant_type": "authorization_code",
        }
    )
    url = f"https://api.weixin.qq.com/sns/jscode2session?{params}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "WECHAT_NETWORK",
                "message": "连接微信登录接口失败，请检查服务器出网后重试。",
            },
        ) from e
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=502,
            detail={"code": "WECHAT_BAD_RESPONSE", "message": "微信登录接口返回无法解析。"},
        ) from e
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=502,
            detail={"code": "WECHAT_BAD_RESPONSE", "message": "微信登录接口返回异常。"},
        )
    errcode = data.get("errcode")
    if errcode not in (None, 0):
        # Never echo secret; errmsg from WeChat is ok
        hint = WECHAT_ERR_HINTS.get(int(errcode)) if str(errcode).lstrip("-").isdigit() else None
        raise HTTPException(
            status_code=401,
            detail={
                "code": "WECHAT_LOGIN_FAILED",
                "message": hint or f"微信登录失败（errcode={errcode}）。",
                "errcode": errcode,
                "errmsg": data.get("errmsg") or "",
            },
        )
    openid = str(data.get("openid") or "").strip()
    if not openid:
        raise HTTPException(
            status_code=401,
            detail={"code": "WECHAT_NO_OPENID", "message": "微信登录未返回 openid。"},
        )
    return {"openid": openid, "session_key_present": bool(data.get("session_key")), "unionid": data.get("unionid")}


def _dev_openid_from_code(code: str) -> str:
    digest = hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]
    return f"dev_openid_{digest}"


@app.post("/api/login")
def login(body: LoginBody):
    """
    Exchange wx.login `code` for a session_token.

    - If WECHAT_APPID + WECHAT_SECRET are set: call WeChat jscode2session (live).
    - Else **dev mode**: accept any code and return a fake openid + token for local testing.
      Documented clearly in response `mode: "dev"`.
    """
    code = (body.code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="缺少 code")

    if WECHAT_LOGIN_READY:
        wx = _wechat_jscode2session(code)
        issued = _issue_session(wx["openid"], mode="live")
        return {
            "ok": True,
            "mode": "live",
            "openid": issued["openid"],
            "session_token": issued["session_token"],
            "token": issued["session_token"],
            "expires_at": issued["expires_at"],
            "expires_in_sec": issued["expires_in_sec"],
            "hint": "真登录成功。后续请求请带 Authorization: Bearer <session_token>，配额按 openid 计算。",
        }

    # Dev mode: no WeChat credentials configured
    openid = _dev_openid_from_code(code)
    issued = _issue_session(openid, mode="dev")
    return {
        "ok": True,
        "mode": "dev",
        "openid": issued["openid"],
        "session_token": issued["session_token"],
        "token": issued["session_token"],
        "expires_at": issued["expires_at"],
        "expires_in_sec": issued["expires_in_sec"],
        "hint": (
            "开发模式：未配置 WECHAT_APPID/WECHAT_SECRET。"
            "任意 code 可换假 openid（dev_openid_*）。"
            "真登录请设置 WECHAT_* 后重启。后续请求请带 Authorization: Bearer <session_token>。"
        ),
    }


@app.get("/api/me")
def me(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"),
):
    ident = _resolve_quota_key(authorization, x_client_id)
    snap = _quota_snapshot(ident["quota_key"])
    return {
        "openid": ident["openid"],
        "client_id": ident["client_id"],
        "auth": ident["auth"],
        "quota_key": ident["quota_key"],
        "wechat_login": "live" if WECHAT_LOGIN_READY else "dev",
        "quota": _quota_public_fields(snap),
    }


@app.get("/api/quota")
def get_quota(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"),
):
    ident = _resolve_quota_key(authorization, x_client_id)
    snap = _quota_snapshot(ident["quota_key"])
    return {
        "client_id": ident["client_id"],
        "openid": ident["openid"],
        "auth": ident["auth"],
        **_quota_public_fields(snap),
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
        raise RuntimeError("Hermes finished but Home.md missing")
    return {
        "engine": "hermes",
        "note": "Hermes agent via run_hermes_organize.sh",
        "stdout_tail": (proc.stdout or "")[-500:],
    }


def _run_organizer(input_dir: Path, output_dir: Path) -> dict:
    """
    Engine selection via ORGANIZE_ENGINE=auto|hermes|script (default auto).
    Container default should be script; auto prefers Hermes when key+script exist.
    Never logs API keys.
    """
    engine_pref = ORGANIZE_ENGINE if ORGANIZE_ENGINE in ("auto", "hermes", "script") else "auto"

    if engine_pref == "script":
        return _run_script_organizer(input_dir, output_dir)

    try_hermes = (
        HERMES_SCRIPT.is_file()
        and os.access(HERMES_SCRIPT, os.X_OK)
        and _has_model_api_key()
    )

    if engine_pref == "hermes":
        if not try_hermes:
            raise HTTPException(
                status_code=503,
                detail="ORGANIZE_ENGINE=hermes but Hermes script or model API key is unavailable",
            )
        try:
            return _run_hermes_organizer(input_dir, output_dir)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Hermes organize failed: {type(exc).__name__}",
            ) from exc

    # auto
    if try_hermes:
        try:
            return _run_hermes_organizer(input_dir, output_dir)
        except Exception as exc:
            print(f"[organize] Hermes unavailable, falling back to script: {type(exc).__name__}")
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
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    x_client_id: Optional[str] = Header(default=None, alias="X-Client-Id"),
):
    """
    Accept multipart .zip of notes and/or multiple files.
    Runs organizer, zips vault, returns job_id for download.
    Quota keyed by openid when Bearer token present; else X-Client-Id.
    """
    ident = _resolve_quota_key(authorization, x_client_id)
    quota = _check_and_consume_quota(ident["quota_key"])

    job_id = uuid.uuid4().hex
    work = Path(tempfile.mkdtemp(prefix=f"job-{job_id}-", dir=str(JOBS_DIR)))
    try:
        input_dir = _collect_upload_to_input(files, work)
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
            "quota_key": ident["quota_key"],
            "openid": ident["openid"],
            "client_id": ident["client_id"],
        }
        return JSONResponse(
            {
                "job_id": job_id,
                "status": "done",
                "download_url": f"/api/download/{job_id}",
                "engine": meta["engine"],
                "file_count": file_count,
                "quota": _quota_public_fields(quota),
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
