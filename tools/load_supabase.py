"""Upsert IBK regulation articles into Supabase public.baseline_chunks.

Run after applying supabase/schema.sql in the Supabase SQL Editor:
    .venv/Scripts/python.exe tools/load_supabase.py --dry-run
    .venv/Scripts/python.exe tools/load_supabase.py

The server-side loader requires SUPABASE_SECRET_KEY (or legacy
SUPABASE_SERVICE_ROLE_KEY). It intentionally refuses publishable/anon keys.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "ibk_converted" / "parsed"
BATCH_SIZE = 200


def get_server_key() -> str:
    key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        candidate = os.getenv("SUPABASE_KEY", "")
        if candidate.startswith("sb_secret_"):
            key = candidate
    if not key:
        raise RuntimeError(
            "Set SUPABASE_SECRET_KEY in .env (sb_secret_...) or legacy "
            "SUPABASE_SERVICE_ROLE_KEY. SUPABASE_KEY may be publishable and is not used for server-side ingestion."
        )
    if key.startswith("sb_publishable_") or (key.startswith("eyJ") and not os.getenv("SUPABASE_SERVICE_ROLE_KEY")):
        raise RuntimeError("A publishable/anon key cannot be used for this server-side loader.")
    return key


def collect_rows() -> list[dict[str, Any]]:
    if not SOURCE_DIR.is_dir():
        raise FileNotFoundError(f"Regulation JSON directory not found: {SOURCE_DIR}")

    rows: list[dict[str, Any]] = []
    for path in sorted(SOURCE_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        doc = payload["doc"]
        doc_type = doc.get("doc_type") or ""
        title = doc.get("title") or doc["id"]
        if title.replace(" ", "") == "\uc815\uad00":
            rank = 6
        elif any(token in doc_type or token in title for token in (
            "\uc138\uce59", "\uc9c0\uce68", "\uc6b4\uc6a9\uae30\uc900", "\uae30\uc900", "\uc6b4\uc601\uae30\uc900"
        )):
            rank = 8
        else:
            rank = 7

        for article in payload.get("articles", []):
            text = (article.get("text") or "").strip()
            if article.get("deleted") or not text:
                continue
            rows.append({
                "id": article["id"],
                "doc_id": doc["id"],
                "doc_title": title,
                "doc_type": doc.get("doc_type"),
                "authority_rank": rank,
                "effective_date": doc.get("date"),
                "article_no": article.get("no") or "",
                "article_title": article.get("title"),
                "chunk_text": text,
                "source_kind": "internal",
                "source_file": doc.get("file") or path.name,
            })

    if not rows:
        raise RuntimeError(f"No usable article rows found in {SOURCE_DIR}")
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Duplicate article IDs found; refusing to upload ambiguous rows.")
    return rows


def request(url: str, key: str, method: str = "GET", body: bytes | None = None) -> int:
    headers = {"apikey": key, "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
        headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return response.status
    except urllib.error.HTTPError as error:
        response_text = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Supabase returned HTTP {error.code} for {method} {urllib.parse.urlsplit(url).path}. "
            f"Response: {response_text[:500]}"
        ) from None
    except urllib.error.URLError as error:
        raise RuntimeError(f"Supabase network request failed: {error.reason}") from None


def main() -> int:
    load_dotenv(ROOT / ".env", override=True)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Parse and count rows without contacting Supabase.")
    args = parser.parse_args()

    rows = collect_rows()
    print(f"Prepared baseline_chunks rows: {len(rows)} (one per non-deleted, non-empty Article)")
    if args.dry_run:
        print("Dry run complete; no network request or database write was made.")
        return 0

    base_url = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    if not base_url.startswith("https://"):
        raise RuntimeError("SUPABASE_URL must be set to the project's https:// URL.")
    key = get_server_key()
    endpoint = base_url + "/rest/v1/baseline_chunks"
    query = urllib.parse.urlencode({"on_conflict": "id"})

    # A table-specific route accepts publishable keys, but writes here require a server secret.
    request(endpoint + "?select=id&limit=1", key)
    for offset in range(0, len(rows), BATCH_SIZE):
        batch = rows[offset : offset + BATCH_SIZE]
        body = json.dumps(batch, ensure_ascii=False).encode("utf-8")
        status = request(endpoint + "?" + query, key, method="POST", body=body)
        print(f"Upserted {min(offset + len(batch), len(rows))}/{len(rows)} rows (HTTP {status})")
    print(f"Supabase load complete: {len(rows)} baseline_chunks rows upserted.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"Load failed: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
