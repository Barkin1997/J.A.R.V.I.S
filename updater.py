from pathlib import Path
import shutil
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parent
BACKUP_DIR = ROOT / "backups"
BACKUP_DIR.mkdir(exist_ok=True)


def backup():
    out = BACKUP_DIR / f"backup_{time.strftime('%Y%m%d_%H%M%S')}.zip"
    skip = {"backups", ".venv", "external", "Jarvis_Projects", "data"}
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in ROOT.rglob("*"):
            if any(part in skip for part in p.relative_to(ROOT).parts):
                continue
            if p.is_file():
                z.write(p, p.relative_to(ROOT))
    return out


def update_from_zip(zip_path: str):
    zpath = Path(zip_path).expanduser()
    if not zpath.exists():
        print("Update-ZIP nicht gefunden:", zpath)
        return 1
    b = backup()
    print("Backup erstellt:", b)
    tmp = ROOT / "_update_tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    with zipfile.ZipFile(zpath, "r") as z:
        z.extractall(tmp)
    base = tmp
    children = [p for p in tmp.iterdir()]
    if len(children) == 1 and children[0].is_dir():
        base = children[0]
    skip = {".env", ".venv", "data", "external", "Jarvis_Projects", "backups"}
    for p in base.rglob("*"):
        rel = p.relative_to(base)
        if rel.parts and rel.parts[0] in skip:
            continue
        target = ROOT / rel
        if p.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
    shutil.rmtree(tmp)
    print("Update fertig.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Nur Backup wird erstellt.")
        print(backup())
    else:
        raise SystemExit(update_from_zip(sys.argv[1]))
