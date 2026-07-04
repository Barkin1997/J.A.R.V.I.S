from pathlib import Path
import shutil, time
ROOT = Path(__file__).resolve().parent

def backup(path):
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + f".backup_{time.strftime('%Y%m%d_%H%M%S')}"))

def patch_config():
    p=ROOT/'config.py'
    if not p.exists(): print('config.py nicht gefunden.'); return
    backup(p); text=p.read_text(encoding='utf-8')
    add='''
VIDEO_OUTPUT_DIR = Path(os.getenv("VIDEO_OUTPUT_DIR", "Jarvis_Projects/ki_videos")).expanduser()
VIDEO_DEFAULT_SECONDS = int(os.getenv("VIDEO_DEFAULT_SECONDS", "4"))
VIDEO_DEFAULT_FPS = int(os.getenv("VIDEO_DEFAULT_FPS", "16"))
VIDEO_DEFAULT_WIDTH = int(os.getenv("VIDEO_DEFAULT_WIDTH", "1024"))
VIDEO_DEFAULT_HEIGHT = int(os.getenv("VIDEO_DEFAULT_HEIGHT", "576"))
VIDEO_MODE = os.getenv("VIDEO_MODE", "ComfyUI")
VIDEO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
'''
    if 'VIDEO_OUTPUT_DIR =' not in text: text += '\n\n' + add
    p.write_text(text, encoding='utf-8'); print('config.py gepatcht.')

def patch_env(name):
    p=ROOT/name
    if not p.exists(): p.write_text('', encoding='utf-8')
    backup(p); text=p.read_text(encoding='utf-8')
    for line in ['VIDEO_OUTPUT_DIR=Jarvis_Projects/ki_videos','VIDEO_DEFAULT_SECONDS=4','VIDEO_DEFAULT_FPS=16','VIDEO_DEFAULT_WIDTH=1024','VIDEO_DEFAULT_HEIGHT=576','VIDEO_MODE=ComfyUI']:
        key=line.split('=',1)[0]
        if key not in text: text += '\n' + line
    p.write_text(text, encoding='utf-8'); print(name + ' gepatcht.')

def patch_brain():
    p=ROOT/'brain.py'
    if not p.exists(): print('brain.py nicht gefunden.'); return
    backup(p); text=p.read_text(encoding='utf-8')
    if 'from skills.video_ai import VideoAISkill' not in text:
        if 'from skills.image_ai import ImageAISkill\n' in text:
            text=text.replace('from skills.image_ai import ImageAISkill\n','from skills.image_ai import ImageAISkill\nfrom skills.video_ai import VideoAISkill\n')
        else:
            text='from skills.video_ai import VideoAISkill\n'+text
    if 'self.video_ai = VideoAISkill()' not in text:
        if 'self.image_ai = ImageAISkill()' in text:
            text=text.replace('        self.image_ai = ImageAISkill()\n','        self.image_ai = ImageAISkill()\n        self.video_ai = VideoAISkill()\n')
        elif 'self.plugins = PluginManager()' in text:
            text=text.replace('        self.plugins = PluginManager()\n','        self.plugins = PluginManager()\n        self.video_ai = VideoAISkill()\n')
    routes='''
        if lower.startswith(("ki video status", "video ai status", "video status")):
            return self.video_ai.status()

        if lower.startswith(("öffne ki video", "oeffne ki video", "öffne video ki", "video ki öffnen", "video ai öffnen")):
            return self.video_ai.open()

        if lower.startswith(("ki video hilfe", "video ki hilfe", "video ai hilfe")):
            return self.video_ai.install_hint()

        if lower.startswith(("erstelle ki video", "ki video erstellen", "ki video generieren", "ai video erstellen", "video generieren")):
            prompt = self._after(command, ["erstelle ki video", "ki video erstellen", "ki video generieren", "ai video erstellen", "video generieren"])
            return self.video_ai.create_video_project(prompt)

'''
    if 'self.video_ai.create_video_project' not in text:
        marker='        lower = command.lower()\n\n'
        if marker in text: text=text.replace(marker, marker+routes, 1)
        else: print('Routing-Stelle nicht gefunden. Bitte brain.py senden.')
    p.write_text(text, encoding='utf-8'); print('brain.py gepatcht.')

print('KI Video Update wird angewendet...')
(ROOT/'skills').mkdir(exist_ok=True)
patch_config(); patch_env('.env.example'); patch_env('.env'); patch_brain()
print('Fertig. Jetzt install_video_ai.bat starten, danach Starte Jarvis KI.bat.')
