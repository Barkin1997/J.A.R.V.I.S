#!/usr/bin/env python3
"""Restore Jarvis full package from downloaded .tar.part files."""

from __future__ import annotations

import argparse
from pathlib import Path
import tarfile


class MultiPartReader:
    def __init__(self, parts: list[Path]) -> None:
        self.parts = parts
        self.index = 0
        self.current = None
        self._open_next()

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        if size == 0:
            return b""
        chunks: list[bytes] = []
        remaining = size
        while self.current is not None and (remaining > 0 or size < 0):
            data = self.current.read(1024 * 1024 if size < 0 else remaining)
            if data:
                chunks.append(data)
                if size > 0:
                    remaining -= len(data)
                continue
            self.current.close()
            self._open_next()
        return b"".join(chunks)

    def _open_next(self) -> None:
        if self.index >= len(self.parts):
            self.current = None
            return
        self.current = self.parts[self.index].open("rb")
        self.index += 1

    def close(self) -> None:
        if self.current:
            self.current.close()
            self.current = None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parts", required=True, help="Folder containing downloaded .tar.part files")
    parser.add_argument("--out", required=True, help="Output folder")
    parser.add_argument("--prefix", default="jarvis_full_with_models_20260703_232834")
    args = parser.parse_args()

    parts_dir = Path(args.parts).resolve()
    parts = sorted(parts_dir.glob(f"{args.prefix}.tar.part*"))
    if not parts:
        raise SystemExit(f"No parts found in {parts_dir}")

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    reader = MultiPartReader(parts)
    try:
        with tarfile.open(fileobj=reader, mode="r|") as tar:
            tar.extractall(out)
    finally:
        reader.close()
    print(f"Restored to: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
