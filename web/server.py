"""Estes — small FastAPI bridge between the marketing/dashboard page
(`web/index.html`) and the real `auditor.scan_skill` engine.

Run with:

    uvicorn web.server:app --reload --port 5173

Endpoints
---------
GET  /                       → serves `web/index.html`
POST /api/scan/file          → multipart upload, runs scan_skill on it
POST /api/scan/url           → JSON `{url: "..."}`, runs scan_skill on it
GET  /api/download/{scan_id} → patched .zip with `estes: ignore` markers
GET  /api/health             → liveness probe

Both scan endpoints return the same JSON shape (`scan_to_payload`). The
frontend renders findings dynamically from this payload.
"""
from __future__ import annotations

import io
import shutil
import sys
import tempfile
import time
import uuid
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

# Allow `import auditor` when running from anywhere.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, File, HTTPException, UploadFile  # noqa: E402
from fastapi.responses import FileResponse, Response  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from auditor import Finding, ScanReport, scan_skill  # noqa: E402

WEB_DIR = Path(__file__).resolve().parent
INDEX = WEB_DIR / "index.html"

# ---------------------------------------------------------------------------
# Score weights — mirrors auditor._SEVERITY_WEIGHT / _CATEGORY_MULTIPLIER so
# the UI can show *why* each finding moved the gauge.
# ---------------------------------------------------------------------------

_SEV_WEIGHT = {"critical": 80, "high": 30, "warning": 10, "info": 2}
_CAT_MULT = {
    "wallet_secret": 2.0, "wallet_action": 1.5, "ssh_key": 1.5,
    "cloud_credential": 1.3, "db_credential": 1.2, "high_value_token": 1.2,
}


def _finding_weight(f: Finding) -> int:
    return int(round(_SEV_WEIGHT.get(f.severity, 0) * _CAT_MULT.get(f.category, 1.0)))


# ---------------------------------------------------------------------------
# In-memory scan store. Key = scan_id (uuid). Holds the materialized upload
# dir so the /api/download endpoint can rebuild a patched zip on demand.
# Entries TTL after 30 minutes.
# ---------------------------------------------------------------------------

_TTL_S = 30 * 60
_STORE: dict[str, dict[str, Any]] = {}


def _gc() -> None:
    now = time.time()
    expired = [sid for sid, ent in _STORE.items() if now - ent["created"] > _TTL_S]
    for sid in expired:
        ent = _STORE.pop(sid, None)
        if ent and ent.get("root"):
            shutil.rmtree(ent["root"], ignore_errors=True)


# ---------------------------------------------------------------------------
# Payload shaping
# ---------------------------------------------------------------------------


def scan_to_payload(scan_id: str, label: str, report: ScanReport,
                    can_download: bool) -> dict[str, Any]:
    """Turn a ScanReport into the JSON shape consumed by index.html."""

    counts = {
        "critical": sum(1 for f in report.findings if f.severity == "critical"),
        "high":     sum(1 for f in report.findings if f.severity == "high"),
        "warning":  sum(1 for f in report.findings if f.severity == "warning"),
        "info":     sum(1 for f in report.findings if f.severity == "info"),
    }

    return {
        "scan_id": scan_id,
        "label": label,
        "risk_score": report.risk_score,
        "severity": report.severity,
        "files_scanned": report.files_scanned,
        "bytes_scanned": report.bytes_scanned,
        "duration_ms": report.duration_ms,
        "llm_used": report.llm_used,
        "llm_provider": report.llm_provider,
        "warnings": list(report.warnings),
        "manifest": asdict(report.manifest),
        "counts": counts,
        "suggested_fix": report.suggested_fix,
        "can_download": can_download,
        "findings": [
            {
                "id": f.id,
                "severity": f.severity,
                "source": f.source,
                "category": f.category,
                "file": f.file,
                "line": f.line,
                "message": f.message,
                "snippet": f.snippet,
                "suggested_fix": f.suggested_fix,
                "weight": _finding_weight(f),
            }
            for f in report.findings
        ],
    }


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Estes Web Bridge", version="1.0.0")


class UrlRequest(BaseModel):
    url: str


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    if not INDEX.exists():
        raise HTTPException(404, "web/index.html missing")
    return FileResponse(INDEX, media_type="text/html")


@app.post("/api/scan/file")
async def scan_file(file: UploadFile = File(...)) -> dict[str, Any]:
    """Persist the upload, run scan_skill on it, return the payload."""
    _gc()
    if not file.filename:
        raise HTTPException(400, "missing filename")

    scan_id = uuid.uuid4().hex
    root = Path(tempfile.mkdtemp(prefix=f"estes_web_{scan_id}_"))
    target = root / file.filename
    target.write_bytes(await file.read())

    try:
        report = scan_skill(target, llm=True)
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(root, ignore_errors=True)
        raise HTTPException(500, f"scan failed: {exc.__class__.__name__}: {exc}")

    _STORE[scan_id] = {
        "report": report, "root": root, "label": file.filename, "created": time.time(),
    }
    return scan_to_payload(scan_id, file.filename, report, can_download=True)


@app.post("/api/scan/url")
def scan_url(req: UrlRequest) -> dict[str, Any]:
    """Run scan_skill on a public GitHub URL."""
    _gc()
    if not req.url.strip():
        raise HTTPException(400, "url is required")

    scan_id = uuid.uuid4().hex
    try:
        report = scan_skill(req.url.strip(), llm=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"scan failed: {exc.__class__.__name__}: {exc}")

    # GitHub scans don't keep a materialized tree (scan_skill cleans up its
    # own temp dir), so download is unavailable for those.
    _STORE[scan_id] = {
        "report": report, "root": None, "label": req.url, "created": time.time(),
    }
    return scan_to_payload(scan_id, req.url, report, can_download=False)


@app.get("/api/download/{scan_id}")
def download(scan_id: str) -> Response:
    """Stub auto-patch: zip up the original tree with `# estes: ignore`
    appended to every flagged line, plus a manifest.

    This intentionally mirrors `app._build_fixed_zip` so behaviour stays
    consistent between the Streamlit UI and this web frontend.
    """
    _gc()
    ent = _STORE.get(scan_id)
    if not ent:
        raise HTTPException(404, "unknown or expired scan_id")
    report: ScanReport = ent["report"]
    root: Path | None = ent["root"]
    if root is None or not root.exists():
        raise HTTPException(409, "download not available for URL scans")

    findings_by_file: dict[str, set[int]] = {}
    for f in report.findings:
        if f.file and f.line:
            findings_by_file.setdefault(f.file, set()).add(f.line)

    def _comment_for(path: str) -> str:
        suffix = Path(path).suffix.lower()
        if suffix in {".py", ".sh", ".rb", ".yaml", ".yml", ".toml", ".env", ".ini"}:
            return "  # estes: ignore"
        if suffix in {".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs", ".go",
                      ".java", ".c", ".cpp", ".h"}:
            return "  // estes: ignore"
        return "  # estes: ignore"

    # Determine the source root (extracted .zip vs raw single file vs dir).
    zips = list(root.glob("*.zip"))
    if zips:
        src_root = root / "_extracted"
        if not src_root.exists():
            src_root.mkdir()
            with zipfile.ZipFile(zips[0]) as zf:
                zf.extractall(src_root)
    else:
        src_root = root

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in src_root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(src_root).as_posix()
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                zf.write(path, arcname=rel)
                continue
            lines = text.splitlines(keepends=True)
            hot = findings_by_file.get(rel, set())
            for ln in hot:
                idx = ln - 1
                if 0 <= idx < len(lines):
                    line = lines[idx].rstrip("\n")
                    if "estes: ignore" not in line:
                        lines[idx] = line + _comment_for(rel) + "\n"
            zf.writestr(rel, "".join(lines))

        sheet = (
            "# Estes patch sheet\n\n"
            f"Source:   {report.source}\n"
            f"Severity: {report.severity}  Score: {report.risk_score}\n"
            f"Findings: {len(report.findings)}\n\n"
            "## Lines marked with `estes: ignore`\n\n"
        )
        for fname, lns in sorted(findings_by_file.items()):
            sheet += f"- {fname}: {sorted(lns)}\n"
        sheet += (
            "\n> **Stub patch — review before redistributing.** This silences "
            "findings, it does not fix the underlying leak.\n"
        )
        zf.writestr("ESTES_PATCH.md", sheet)

    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="skill_fixed.zip"'},
    )
