import asyncio
import logging
import re
from pathlib import Path

import httpx

from bot.config import YANDEX_DISK_TOKEN, YANDEX_DISK_ROOT
from bot.services.database import (
    enqueue_upload,
    get_pending_uploads,
    update_upload_attempt,
    delete_upload_queue_entry,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://cloud-api.yandex.net/v1/disk/resources"
_HEADERS = {"Authorization": f"OAuth {YANDEX_DISK_TOKEN}"}
_MAX_ATTEMPTS = 3


def _sanitize(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name)


def _image_remote_path(chat_title: str, date_str: str, message_id: int, filename: str) -> str:
    chat_folder = _sanitize(chat_title)
    return f"{YANDEX_DISK_ROOT}/{chat_folder}/{date_str}/images/{message_id}_{filename}"


def _links_remote_path(chat_title: str, date_str: str) -> str:
    chat_folder = _sanitize(chat_title)
    return f"{YANDEX_DISK_ROOT}/{chat_folder}/{date_str}/links.txt"


async def _ensure_path(client: httpx.AsyncClient, path: str) -> None:
    """Create all intermediate directories on Yandex Disk."""
    parts = [p for p in Path(path).parent.parts if p != "/"]
    current = ""
    for part in parts:
        current = f"{current}/{part}"
        resp = await client.put(_BASE_URL, params={"path": current}, headers=_HEADERS)
        if resp.status_code not in (201, 409):
            resp.raise_for_status()


async def _get_upload_url(client: httpx.AsyncClient, remote_path: str) -> str:
    resp = await client.get(
        f"{_BASE_URL}/upload",
        params={"path": remote_path, "overwrite": "true"},
        headers=_HEADERS,
    )
    resp.raise_for_status()
    return resp.json()["href"]


async def _upload_bytes(client: httpx.AsyncClient, upload_url: str, data: bytes) -> None:
    resp = await client.put(upload_url, content=data)
    resp.raise_for_status()


async def _upload_with_retry(remote_path: str, data: bytes, *, attempt: int = 0) -> None:
    delay = 2 ** attempt
    for i in range(attempt, _MAX_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                await _ensure_path(client, remote_path)
                url = await _get_upload_url(client, remote_path)
                await _upload_bytes(client, url, data)
            logger.info("Uploaded to Yandex Disk: %s", remote_path)
            return
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                wait = int(exc.response.headers.get("Retry-After", delay * 2))
                logger.warning("Yandex Disk rate-limited, waiting %ds", wait)
                await asyncio.sleep(wait)
            else:
                logger.warning("Upload attempt %d failed for %s: %s", i + 1, remote_path, exc)
                await asyncio.sleep(delay)
                delay *= 2
        except Exception as exc:
            logger.warning("Upload attempt %d failed for %s: %s", i + 1, remote_path, exc)
            await asyncio.sleep(delay)
            delay *= 2
    raise RuntimeError(f"All {_MAX_ATTEMPTS} upload attempts failed for {remote_path}")


async def upload_image(
    chat_title: str,
    date_str: str,
    message_id: int,
    filename: str,
    data: bytes,
) -> None:
    remote = _image_remote_path(chat_title, date_str, message_id, filename)
    try:
        await _upload_with_retry(remote, data)
    except Exception as exc:
        local = _save_pending(filename, data)
        await enqueue_upload(str(local), remote)
        logger.error("Permanently failed to upload image %s, queued: %s", remote, exc)


async def append_link(
    chat_title: str,
    date_str: str,
    time_str: str,
    username: str,
    url: str,
    context: str,
) -> None:
    line = f"[{time_str}] @{username}: {url} — {context}\n"
    remote = _links_remote_path(chat_title, date_str)
    try:
        existing = await _download_text(remote)
    except Exception:
        existing = ""
    combined = (existing + line).encode("utf-8")
    try:
        await _upload_with_retry(remote, combined)
    except Exception as exc:
        logger.error("Failed to append link to Yandex Disk %s: %s", remote, exc)


async def _download_text(remote_path: str) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_BASE_URL}/download",
            params={"path": remote_path},
            headers=_HEADERS,
        )
        if resp.status_code == 404:
            return ""
        resp.raise_for_status()
        dl_url = resp.json()["href"]
        dl = await client.get(dl_url)
        dl.raise_for_status()
        return dl.text


def _save_pending(filename: str, data: bytes) -> Path:
    pending = Path("pending")
    pending.mkdir(exist_ok=True)
    dest = pending / filename
    dest.write_bytes(data)
    return dest


async def process_upload_queue() -> None:
    items = await get_pending_uploads()
    for item in items:
        local = Path(item["local_path"])
        if not local.exists():
            await delete_upload_queue_entry(item["id"])
            continue
        try:
            data = local.read_bytes()
            await _upload_with_retry(item["remote_path"], data, attempt=item["attempts"])
            local.unlink(missing_ok=True)
            await delete_upload_queue_entry(item["id"])
            logger.info("Queued upload succeeded: %s", item["remote_path"])
        except Exception as exc:
            await update_upload_attempt(item["id"], str(exc))
            logger.error("Queued upload still failing: %s — %s", item["remote_path"], exc)
