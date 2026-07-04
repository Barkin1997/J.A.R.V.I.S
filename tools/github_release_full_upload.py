#!/usr/bin/env python3
"""Upload the full Jarvis package to GitHub Releases as split tar parts.

The normal Git repository stays small. This script streams the full local
package into tar parts under GitHub's release-asset limit and uploads each part.
It only needs temporary disk space for one part at a time.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import time
from typing import BinaryIO

try:
    import requests
except ImportError as exc:  # pragma: no cover - user environment helper
    raise SystemExit("Install requests first: pip install requests") from exc


GITHUB_API = "https://api.github.com"
GITHUB_UPLOADS = "https://uploads.github.com"


class ReleaseClient:
    def __init__(self, owner: str, repo: str, token: str) -> None:
        self.owner = owner
        self.repo = repo
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "jarvis-full-release-uploader",
            }
        )

    def get_release_by_tag(self, tag: str) -> dict | None:
        url = f"{GITHUB_API}/repos/{self.owner}/{self.repo}/releases/tags/{tag}"
        res = self.session.get(url, timeout=60)
        if res.status_code == 404:
            return None
        res.raise_for_status()
        return res.json()

    def create_release(self, tag: str, name: str, body: str, draft: bool) -> dict:
        existing = self.get_release_by_tag(tag)
        if existing:
            print(f"Using existing release: {existing['html_url']}")
            return existing
        url = f"{GITHUB_API}/repos/{self.owner}/{self.repo}/releases"
        payload = {
            "tag_name": tag,
            "target_commitish": "main",
            "name": name,
            "body": body,
            "draft": draft,
            "prerelease": False,
        }
        res = self.session.post(url, json=payload, timeout=60)
        res.raise_for_status()
        release = res.json()
        print(f"Created release: {release['html_url']}")
        return release

    def upload_asset(self, release_id: int, path: Path, asset_name: str) -> None:
        url = f"{GITHUB_UPLOADS}/repos/{self.owner}/{self.repo}/releases/{release_id}/assets"
        params = {"name": asset_name}
        headers = {"Content-Type": "application/octet-stream"}
        size = path.stat().st_size
        for attempt in range(1, 4):
            with path.open("rb") as fh:
                res = self.session.post(
                    url,
                    params=params,
                    headers=headers,
                    data=fh,
                    timeout=None,
                )
            if res.status_code in (200, 201):
                print(f"Uploaded {asset_name} ({size / 1024 / 1024:.1f} MiB)")
                return
            if res.status_code == 422 and "already_exists" in res.text:
                print(f"Already exists, skipping: {asset_name}")
                return
            print(f"Upload failed attempt {attempt}: {res.status_code} {res.text[:300]}")
            time.sleep(10 * attempt)
        res.raise_for_status()


class ChunkedTarUploader:
    def __init__(
        self,
        client: ReleaseClient,
        release_id: int,
        prefix: str,
        temp_dir: Path,
        max_bytes: int,
    ) -> None:
        self.client = client
        self.release_id = release_id
        self.prefix = prefix
        self.temp_dir = temp_dir
        self.max_bytes = max_bytes
        self.part_index = 0
        self.current: BinaryIO | None = None
        self.current_path: Path | None = None
        self.current_size = 0
        self.parts: list[str] = []
        self._open_next()

    def writable(self) -> bool:
        return True

    def tell(self) -> int:
        return sum(self.max_bytes for _ in range(self.part_index - 1)) + self.current_size

    def write(self, data: bytes) -> int:
        written = 0
        view = memoryview(data)
        while written < len(data):
            space = self.max_bytes - self.current_size
            if space <= 0:
                self._finish_current()
                self._open_next()
                space = self.max_bytes
            chunk = view[written : written + min(space, len(data) - written)]
            assert self.current is not None
            self.current.write(chunk)
            size = len(chunk)
            self.current_size += size
            written += size
        return written

    def flush(self) -> None:
        if self.current:
            self.current.flush()

    def close(self) -> None:
        if self.current:
            self._finish_current()

    def _open_next(self) -> None:
        self.part_index += 1
        name = f"{self.prefix}.tar.part{self.part_index:04d}"
        self.current_path = self.temp_dir / name
        self.current = self.current_path.open("wb")
        self.current_size = 0
        print(f"Writing {name}")

    def _finish_current(self) -> None:
        assert self.current is not None and self.current_path is not None
        self.current.close()
        self.current = None
        if self.current_path.stat().st_size == 0:
            self.current_path.unlink(missing_ok=True)
            return
        asset_name = self.current_path.name
        self.client.upload_asset(self.release_id, self.current_path, asset_name)
        self.parts.append(asset_name)
        self.current_path.unlink(missing_ok=True)


def add_tree(tar: tarfile.TarFile, root: Path) -> tuple[int, int]:
    count = 0
    total = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        tar.add(path, arcname=rel, recursive=False)
        count += 1
        total += path.stat().st_size
        if count % 1000 == 0:
            print(f"Packed {count} files, {total / 1024 / 1024 / 1024:.2f} GiB")
    return count, total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", required=True, help="Path to Jarvis_FULL_WITH_MODELS folder")
    parser.add_argument("--owner", default="Barkin1997")
    parser.add_argument("--repo", default="J.A.R.V.I.S")
    parser.add_argument("--tag", default="jarvis-full-models-20260704")
    parser.add_argument("--name", default="Jarvis Full Package With Models")
    parser.add_argument("--chunk-mib", type=int, default=1800)
    parser.add_argument("--prefix", default="jarvis_full_with_models_20260703_232834")
    parser.add_argument("--draft", action="store_true", help="Create release as draft")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Missing GITHUB_TOKEN environment variable.", file=sys.stderr)
        print("Create a GitHub token with repo/content release permission and run:", file=sys.stderr)
        print("  set GITHUB_TOKEN=YOUR_TOKEN", file=sys.stderr)
        return 2

    full = Path(args.full).resolve()
    if not full.exists() or not full.is_dir():
        print(f"Full package not found: {full}", file=sys.stderr)
        return 2

    body = (
        "Full Jarvis package with local AI models. "
        "Download all .tar.part files and use tools/restore_full_release_package.py."
    )
    client = ReleaseClient(args.owner, args.repo, token)
    release = client.create_release(args.tag, args.name, body, args.draft)

    max_bytes = args.chunk_mib * 1024 * 1024
    with tempfile.TemporaryDirectory(prefix="jarvis_release_parts_") as temp:
        writer = ChunkedTarUploader(
            client=client,
            release_id=int(release["id"]),
            prefix=args.prefix,
            temp_dir=Path(temp),
            max_bytes=max_bytes,
        )
        with tarfile.open(fileobj=writer, mode="w|") as tar:
            count, total = add_tree(tar, full)
        writer.close()

    manifest = {
        "prefix": args.prefix,
        "tag": args.tag,
        "files": count,
        "total_bytes": total,
        "chunk_mib": args.chunk_mib,
        "restore": "python tools/restore_full_release_package.py --parts PATH_TO_DOWNLOADED_PARTS --out Jarvis_FULL_WITH_MODELS",
    }
    manifest_path = Path(tempfile.gettempdir()) / f"{args.prefix}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    client.upload_asset(int(release["id"]), manifest_path, manifest_path.name)
    manifest_path.unlink(missing_ok=True)
    print("Done.")
    print(release["html_url"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
