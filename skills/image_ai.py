import base64
import os
import re
import shutil
import subprocess
import time
import webbrowser
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

from config import (
    BASE_DIR,
    PROJECT_DIR,
    IMAGE_API_URL,
    IMAGE_WIDTH,
    IMAGE_HEIGHT,
    IMAGE_STEPS,
    IMAGE_CFG_SCALE,
    IMAGE_SAMPLER,
)


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

STYLE_PRESETS = {
    "jarvis": "futuristic orange black Jarvis interface, glowing orange accents, sci fi HUD, holographic detail",
    "realistisch": "photorealistic, realistic textures, natural light, high detail",
    "cinematic": "cinematic lighting, dramatic composition, depth of field, film still",
    "anime": "high quality anime style, clean line art, vibrant lighting",
    "logo": "clean logo design, centered composition, sharp edges, transparent background style",
    "game": "game concept art, readable silhouette, dynamic pose, high detail",
    "portrait": "detailed portrait, expressive face, sharp eyes, professional lighting",
    "wallpaper": "ultra wide wallpaper composition, high detail, atmospheric lighting",
}


class ImageAISkill:
    def __init__(self):
        self.output_dir = PROJECT_DIR / "ki_bilder"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.auto_start = os.getenv("JARVIS_IMAGE_AUTO_START", "1") == "1"
        self.default_2k = os.getenv("JARVIS_IMAGE_DEFAULT_4K", os.getenv("JARVIS_IMAGE_DEFAULT_2K", "1")) == "1"
        self.target_2k_size = int(os.getenv("JARVIS_IMAGE_TARGET_SIZE", os.getenv("JARVIS_IMAGE_2K_SIZE", "4096")))

    def status(self) -> str:
        ok, message = self._ensure_running(wait_seconds=5)
        if ok:
            return (
                f"KI-Bildgenerator bereit: {IMAGE_API_URL}\n"
                f"Ausgabeordner: {self.output_dir}\n"
                f"Stile: {', '.join(STYLE_PRESETS)}"
            )
        return message

    def styles(self) -> str:
        return "KI-Bild-Stile:\n" + "\n".join(f"- {name}: {text}" for name, text in STYLE_PRESETS.items())

    def studio(self) -> str:
        return (
            "KI-BILD STUDIO\n"
            f"Ausgabeordner: {self.output_dir}\n"
            "Bereit fuer: Text-zu-Bild, Referenzbild/Bild-zu-Bild, 2K/4K-Upscale, Style-Presets, Galerie.\n"
            "Style-Presets: " + ", ".join(STYLE_PRESETS.keys()) + "\n\n"
            "Befehle:\n"
            "- Jarvis, erstelle KI Bild realistisch ...\n"
            "- Jarvis, erstelle KI Bild anime ...\n"
            "- Jarvis, erstelle KI Bild cyberpunk/Jarvis ...\n"
            "- Jarvis, erstelle KI Bild mit Referenz C:\\Pfad\\bild.png ...\n"
            "- Jarvis, upscale Bild C:\\Pfad\\bild.png 4K\n"
            "- Jarvis, KI Bild Galerie\n"
            "- Jarvis, KI Bild aussortieren"
        )

    def gallery(self, limit: int = 20) -> str:
        files = self._gallery_files(limit)
        try:
            webbrowser.open(self.output_dir.resolve().as_uri(), new=2)
        except Exception:
            pass
        if not files:
            return f"KI-Bild Galerie ist leer.\nOrdner: {self.output_dir}"
        rows = []
        for path in files:
            meta = self._image_meta(path)
            rows.append(f"- {path.name}: {meta}")
        return "KI-Bild Galerie:\n" + "\n".join(rows) + f"\nOrdner: {self.output_dir}"

    def sort_gallery(self, min_size: int = 512) -> str:
        bad_dir = self.output_dir / "aussortiert"
        bad_dir.mkdir(parents=True, exist_ok=True)
        moved = []
        kept = 0
        for path in self._gallery_files(limit=500):
            if path.parent == bad_dir:
                continue
            ok = self._image_ok(path, min_size=min_size)
            if ok:
                kept += 1
                continue
            target = bad_dir / path.name
            if target.exists():
                target = bad_dir / f"{path.stem}_{int(time.time())}{path.suffix}"
            try:
                shutil.move(str(path), str(target))
                moved.append(target.name)
            except Exception:
                pass
        return (
            "KI-Bild Aussortieren fertig.\n"
            f"Behalten: {kept}\n"
            f"Aussortiert: {len(moved)}\n"
            f"Ordner: {bad_dir}"
        )

    def create_image(self, prompt_de: str, negative_prompt: str = "", reference_path: str = "") -> str:
        prompt_de = (prompt_de or "").strip()
        prompt_de, detected_reference = self._extract_reference(prompt_de, reference_path)
        reference_path = detected_reference or reference_path
        if not prompt_de and not reference_path:
            return "Bildbeschreibung fehlt."

        if reference_path and self._wants_upscale(prompt_de):
            return self.upscale_image(reference_path)

        ok, message = self._ensure_running()
        if not ok:
            return message

        english_prompt = self._improve_prompt(prompt_de or "improve this image")
        quality = self._quality_settings(prompt_de)
        payload = {
            "prompt": english_prompt,
            "negative_prompt": negative_prompt or (
                "low quality, blurry, distorted, bad anatomy, ugly, watermark, text, logo, jpeg artifacts"
            ),
            "steps": quality["steps"],
            "cfg_scale": IMAGE_CFG_SCALE,
            "width": quality["width"],
            "height": quality["height"],
            "sampler_name": IMAGE_SAMPLER,
            "batch_size": 1,
            "n_iter": 1,
            "restore_faces": False,
            "send_images": True,
            "save_images": False,
        }

        endpoint = "txt2img"
        if reference_path:
            img_b64 = self._image_file_to_b64(reference_path)
            if not img_b64:
                return f"Referenzbild nicht gefunden oder nicht lesbar: {reference_path}"
            endpoint = "img2img"
            payload["init_images"] = [img_b64]
            payload["denoising_strength"] = 0.45

        try:
            r = requests.post(f"{IMAGE_API_URL}/sdapi/v1/{endpoint}", json=payload, timeout=900)
            r.raise_for_status()
            data = r.json()
        except requests.exceptions.ConnectionError:
            return self._not_ready_message()
        except Exception as e:
            return f"Bild konnte nicht erstellt werden: {e}"

        images = data.get("images", [])
        if not images:
            return "Kein Bild vom Generator erhalten."

        saved = self._save_images(images, "bild")
        first = saved[0]
        quality_label = f"{quality['width']}x{quality['height']}"
        if quality["upscale_to_2k"]:
            upscaled = self._upscale_image_b64(images[0], quality["upscale_factor"], "bild_4k")
            if upscaled:
                first = upscaled
                quality_name = "4K" if max(quality["target_width"], quality["target_height"]) >= 3840 else "2K"
                quality_label = f"{quality_name} {quality['target_width']}x{quality['target_height']}"
        self._open_file(first)
        mode = "img2img mit Referenzbild" if reference_path else "txt2img"
        return (
            "KI-Bild erstellt.\n"
            f"Modus: {mode}\n"
            f"Qualitaet: {quality_label}\n"
            f"Datei: {first}\n\n"
            f"Verwendeter Prompt:\n{english_prompt}"
        )

    def upscale_image(self, path_text: str) -> str:
        ok, message = self._ensure_running()
        if not ok:
            return message
        image_b64 = self._image_file_to_b64(path_text)
        if not image_b64:
            return f"Bild nicht gefunden oder nicht lesbar: {path_text}"
        payload = {
            "resize_mode": 0,
            "show_extras_results": True,
            "gfpgan_visibility": 0,
            "codeformer_visibility": 0,
            "codeformer_weight": 0,
            "upscaling_resize": 2,
            "upscaler_1": self._best_upscaler(),
            "image": image_b64,
        }
        try:
            r = requests.post(f"{IMAGE_API_URL}/sdapi/v1/extra-single-image", json=payload, timeout=900)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            return f"Upscale konnte nicht erstellt werden: {e}"
        img = data.get("image")
        if not img:
            return "Upscale hat kein Bild geliefert."
        saved = self._save_images([img], "upscale")
        self._open_file(saved[0])
        return f"KI-Upscale fertig.\nDatei: {saved[0]}"

    def _upscale_image_b64(self, image_b64: str, resize: float, prefix: str):
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]
        payload = {
            "resize_mode": 0,
            "show_extras_results": True,
            "gfpgan_visibility": 0,
            "codeformer_visibility": 0,
            "codeformer_weight": 0,
            "upscaling_resize": resize,
            "upscaler_1": self._best_upscaler(),
            "image": image_b64,
        }
        try:
            r = requests.post(f"{IMAGE_API_URL}/sdapi/v1/extra-single-image", json=payload, timeout=900)
            r.raise_for_status()
            data = r.json()
        except Exception:
            return None
        img = data.get("image")
        if not img:
            return None
        saved = self._save_images([img], prefix)
        return saved[0] if saved else None

    def _best_upscaler(self) -> str:
        try:
            r = requests.get(f"{IMAGE_API_URL}/sdapi/v1/upscalers", timeout=8)
            r.raise_for_status()
            names = [item.get("name", "") for item in r.json()]
        except Exception:
            names = []
        for preferred in ("R-ESRGAN 4x+", "R-ESRGAN 4x+ Anime6B", "Lanczos"):
            if preferred in names:
                return preferred
        return names[0] if names else "Lanczos"

    def _ensure_running(self, wait_seconds: int = 90):
        if self._api_ok():
            return True, ""
        if not self.auto_start:
            return False, self._not_ready_message()
        bat = BASE_DIR / "start_image_generator.bat"
        if not bat.exists():
            return False, self._not_ready_message()
        try:
            subprocess.Popen(
                ["cmd.exe", "/c", "start", "Jarvis Bild KI", "/min", str(bat)],
                cwd=str(BASE_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            return False, self._not_ready_message()
        deadline = time.time() + max(1, wait_seconds)
        while time.time() < deadline:
            if self._api_ok():
                return True, ""
            time.sleep(3)
        return (
            False,
            "KI-Bildgenerator wurde gestartet, ist aber noch nicht bereit.\n"
            "Warte kurz und sage dann nochmal: Jarvis, erstelle KI Bild ...\n"
            f"Erwartete Adresse: {IMAGE_API_URL}",
        )

    def _api_ok(self) -> bool:
        try:
            r = requests.get(f"{IMAGE_API_URL}/sdapi/v1/options", timeout=4)
            return bool(r.ok)
        except Exception:
            return False

    def _not_ready_message(self) -> str:
        return (
            "KI-Bildgenerator laeuft nicht.\n"
            "Starte: start_image_generator.bat\n"
            "Dann erneut: Jarvis, erstelle KI Bild ...\n"
            f"Erwartete Adresse: {IMAGE_API_URL}"
        )

    def _save_images(self, images, prefix: str):
        saved = []
        for i, img_b64 in enumerate(images, start=1):
            if "," in img_b64:
                img_b64 = img_b64.split(",", 1)[1]
            raw = base64.b64decode(img_b64)
            img = Image.open(BytesIO(raw))
            file = self.output_dir / f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}_{i}.png"
            img.save(file)
            saved.append(file)
        return saved

    def _gallery_files(self, limit: int = 20):
        if not self.output_dir.exists():
            return []
        files = [
            p for p in self.output_dir.glob("*")
            if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
        ]
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return files[:limit]

    def _image_meta(self, path: Path) -> str:
        try:
            with Image.open(path) as img:
                return f"{img.width}x{img.height}"
        except Exception:
            return "nicht lesbar"

    def _image_ok(self, path: Path, min_size: int = 512) -> bool:
        try:
            with Image.open(path) as img:
                img.verify()
            with Image.open(path) as img:
                return img.width >= min_size and img.height >= min_size
        except Exception:
            return False

    def _open_file(self, path: Path) -> None:
        try:
            webbrowser.open(path.resolve().as_uri(), new=2)
        except Exception:
            pass

    def _image_file_to_b64(self, path_text: str) -> str:
        path = self._clean_path(path_text)
        if not path or not path.exists() or path.suffix.lower() not in IMAGE_SUFFIXES:
            return ""
        try:
            return base64.b64encode(path.read_bytes()).decode("ascii")
        except Exception:
            return ""

    def _extract_reference(self, text: str, explicit: str = ""):
        if explicit:
            return text.strip(), explicit
        raw = text or ""
        if "|" in raw:
            left, right = raw.split("|", 1)
            left_path = self._clean_path(left.replace("referenz", "", 1).replace("ref", "", 1).strip())
            if left_path and left_path.suffix.lower() in IMAGE_SUFFIXES:
                return right.strip(), str(left_path)
        pattern = r'(?:referenz|reference|ref|mit bild|mit foto)\s*[:=]?\s*("[^"]+\.(?:png|jpg|jpeg|webp|bmp)"|\S+\.(?:png|jpg|jpeg|webp|bmp))'
        match = re.search(pattern, raw, flags=re.I)
        if not match:
            return raw.strip(), ""
        ref = self._clean_path(match.group(1))
        cleaned = (raw[: match.start()] + raw[match.end() :]).strip(" |:-")
        return cleaned, str(ref) if ref else ""

    def _clean_path(self, text: str):
        value = (text or "").strip().strip('"').strip("'")
        if not value:
            return None
        try:
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = BASE_DIR / path
            return path
        except Exception:
            return None

    def _wants_upscale(self, text: str) -> bool:
        low = (text or "").lower()
        return any(word in low for word in ["upscale", "hochskalier", "schaerfer", "schärfer", "4k", "verbessere"])

    def _quality_settings(self, text: str):
        low = (text or "").lower()
        wants_fast = any(word in low for word in ["schnell", "quick", "test", "klein"])
        wants_2k = self.default_2k or any(
            word in low
            for word in ["2k", "4k", "2048", "4096", "qualitaet", "qualität", "hochqualitaet", "hochqualität", "ultra"]
        )
        width = min(IMAGE_WIDTH, 1024)
        height = min(IMAGE_HEIGHT, 1024)
        target_width = self.target_2k_size if width >= height else int(width * (self.target_2k_size / max(height, 1)))
        target_height = self.target_2k_size if height >= width else int(height * (self.target_2k_size / max(width, 1)))
        factor = max(target_width / max(width, 1), target_height / max(height, 1))
        return {
            "width": width,
            "height": height,
            "steps": max(IMAGE_STEPS, 34) if wants_2k and not wants_fast else IMAGE_STEPS,
            "upscale_to_2k": wants_2k and not wants_fast,
            "target_width": target_width,
            "target_height": target_height,
            "upscale_factor": round(factor, 2),
        }

    def _improve_prompt(self, text: str) -> str:
        base = (text or "").strip()
        low = base.lower()
        additions = [
            "high quality",
            "detailed",
            "sharp focus",
            "professional composition",
            "4k",
            "realistic textures",
        ]
        for name, preset in STYLE_PRESETS.items():
            if name in low:
                additions.append(preset)
        if any(word in low for word in ["jarvis", "orange", "futuristisch", "hud", "ki"]):
            additions.append(STYLE_PRESETS["jarvis"])
        return f"{base}, {', '.join(dict.fromkeys(additions))}"
