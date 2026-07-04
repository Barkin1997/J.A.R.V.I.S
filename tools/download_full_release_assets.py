#!/usr/bin/env python3
"""Download all Jarvis full-model release parts from GitHub Releases."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import time

try:
    import requests
except ImportError as exc:
    raise SystemExit("Install requests first: python -m pip install requests") from exc


GITHUB_API = "https://api.github.com"


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "jarvis-full-release-downloader",
        }
    )
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    return s


def get_release(s: requests.Session, owner: str, repo: str, tag: str) -> dict:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/releases/tags/{tag}"
    res = s.get(url, timeout=60)
    if res.status_code == 404:
        raise SystemExit(
            f"Release not found: {tag}\n"
            "The model release has not been published yet."
        )
    res.raise_for_status()
    return res.json()


def list_assets(s: requests.Session, owner: str, repo: str, release_id: int) -> list[dict]:
    all_assets: list[dict] = []
    page = 1
    while True:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/releases/{release_id}/assets"
        res = s.get(url, params={"per_page": 100, "page": page}, timeout=60)
        res.raise_for_status()
        assets = res.json()
        if not assets:
            break
        all_assets.extend(assets)
        page += 1
    return all_assets


def download_asset(s: requests.Session, asset: dict, out: Path) -> None:
    name = asset["name"]
    target = out / name
    size = int(asset.get("size") or 0)
    if target.exists() and target.stat().st_size == size:
        print(f"OK exists: {name}")
        return

    print(f"Downloading: {name} ({size / 1024 / 1024:.1f} MiB)")
    headers = dict(s.headers)
    headers["Accept"] = "application/octet-stream"
    for attempt in range(1, 4):
        with s.get(asset["url"], headers=headers, stream=True, timeout=60) as res:
            if res.status_code in (301, 302, 303, 307, 308):
                # requests usually follows redirects, this is just defensive.
                pass
            res.raise_for_status()
            tmp = target.with_suffix(target.suffix + ".download")
            with tmp.open("wb") as fh:
                for chunk in res.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        fh.write(chunk)
            tmp.replace(target)
            return
        print(f"Retry {attempt}/3 for {name}")
        time.sleep(10 * attempt)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner", default="Barkin1997")
    parser.add_argument("--repo", default="J.A.R.V.I.S")
    parser.add_argument("--tag", default="jarvis-full-models-20260704")
    parser.add_argument("--prefix", default="jarvis_full_with_models_20260703_232834")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    s = session()
    release = get_release(s, args.owner, args.repo, args.tag)
    assets = list_assets(s, args.owner, args.repo, int(release["id"]))
    wanted = [
        a for a in assets
        if a["name"].startswith(args.prefix + ".tar.part")
        or a["name"].startswith(args.prefix + "_manifest")
    ]
    if not wanted:
        raise SystemExit("No matching model assets found in the release.")

    for asset in sorted(wanted, key=lambda a: a["name"]):
        download_asset(s, asset, out)

    print(f"Downloaded {len(wanted)} assets to: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
