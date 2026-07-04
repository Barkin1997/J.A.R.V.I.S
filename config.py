import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

def project_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else BASE_DIR / path

ASSISTANT_NAME = os.getenv("ASSISTANT_NAME", "Jarvis")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_TEXT_MODEL = os.getenv("OLLAMA_TEXT_MODEL", "qwen3-coder-next:latest")
OLLAMA_CODE_MODEL = os.getenv("OLLAMA_CODE_MODEL", "qwen3-coder-next:latest")
OLLAMA_MAX_CODE_MODEL = os.getenv("OLLAMA_MAX_CODE_MODEL", "qwen3-coder-next:latest")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava:13b")
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "16384"))
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.15"))
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "900"))

PROJECT_DIR = Path(os.getenv("PROJECT_DIR", "Jarvis_Projects")).expanduser()
MEMORY_DB = Path(os.getenv("MEMORY_DB", "data/memory.sqlite")).expanduser()
VOICE_RATE = int(os.getenv("VOICE_RATE", "165"))
VOICE_VOLUME = float(os.getenv("VOICE_VOLUME", "1.0"))
RECORD_SECONDS = int(os.getenv("RECORD_SECONDS", "5"))
VOSK_MODEL_DIR = project_path(os.getenv("VOSK_MODEL_DIR", "models/vosk-model-small-de-0.15"))
BROWSER_USER_DATA = Path(os.getenv("BROWSER_USER_DATA", "data/browser_profile"))

PROJECT_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
BROWSER_USER_DATA.mkdir(parents=True, exist_ok=True)


IMAGE_API_URL = os.getenv("IMAGE_API_URL", "http://127.0.0.1:7860").rstrip("/")
IMAGE_MODEL_HINT = os.getenv("IMAGE_MODEL_HINT", "SDXL")
IMAGE_WIDTH = int(os.getenv("IMAGE_WIDTH", "1024"))
IMAGE_HEIGHT = int(os.getenv("IMAGE_HEIGHT", "1024"))
IMAGE_STEPS = int(os.getenv("IMAGE_STEPS", "30"))
IMAGE_CFG_SCALE = float(os.getenv("IMAGE_CFG_SCALE", "7"))
IMAGE_SAMPLER = os.getenv("IMAGE_SAMPLER", "DPM++ 2M Karras")


OLLAMA_AGENT_CODE_MODEL = os.getenv("OLLAMA_AGENT_CODE_MODEL", "qwen3-coder-next:latest")
OLLAMA_STRONG_CODE_MODEL = os.getenv("OLLAMA_STRONG_CODE_MODEL", "qwen3-coder-next:latest")
OLLAMA_BEAST_CODE_MODEL = os.getenv("OLLAMA_BEAST_CODE_MODEL", "qwen3-coder-next:latest")
AUTO_BUILD_TEST = os.getenv("AUTO_BUILD_TEST", "1") == "1"
AUTO_FIX_ROUNDS = int(os.getenv("AUTO_FIX_ROUNDS", "2"))
AUTO_GIT_SNAPSHOT = os.getenv("AUTO_GIT_SNAPSHOT", "1") == "1"


RAG_DB = Path(os.getenv("RAG_DB", "data/rag.sqlite")).expanduser()
RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "1200"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "6"))
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text-v2-moe")
REPO_MAX_FILES = int(os.getenv("REPO_MAX_FILES", "80"))
REPO_MAX_FILE_CHARS = int(os.getenv("REPO_MAX_FILE_CHARS", "12000"))
BROWSER_AGENT_MAX_STEPS = int(os.getenv("BROWSER_AGENT_MAX_STEPS", "6"))
BROWSER_AGENT_BLOCK_SUBMIT = os.getenv("BROWSER_AGENT_BLOCK_SUBMIT", "1") == "1"
COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
COMFYUI_DIR = Path(os.getenv("COMFYUI_DIR", "external/ComfyUI")).expanduser()

RAG_DB.parent.mkdir(parents=True, exist_ok=True)


REQUIRE_WAKE_WORD = os.getenv("REQUIRE_WAKE_WORD", "1") == "1"
WAKE_WORD = os.getenv("WAKE_WORD", "jarvis").lower().strip()



MULTI_AGENT_MODEL = os.getenv("MULTI_AGENT_MODEL", "qwen3-coder-next:latest")
PLANNER_MODEL = os.getenv("PLANNER_MODEL", MULTI_AGENT_MODEL)
TESTER_MODEL = os.getenv("TESTER_MODEL", MULTI_AGENT_MODEL)
FIXER_MODEL = os.getenv("FIXER_MODEL", MULTI_AGENT_MODEL)
SECURITY_MODEL = os.getenv("SECURITY_MODEL", MULTI_AGENT_MODEL)
FEEDBACK_MODEL = os.getenv("FEEDBACK_MODEL", FIXER_MODEL)
INTERNET_RESEARCH_MODEL = os.getenv("INTERNET_RESEARCH_MODEL", MULTI_AGENT_MODEL)
PROJECT_MEMORY_DB = Path(os.getenv("PROJECT_MEMORY_DB", "data/project_memory.sqlite")).expanduser()
TASK_DB = Path(os.getenv("TASK_DB", "data/tasks.sqlite")).expanduser()
WEB_MEMORY_AUTO_INDEX = os.getenv("WEB_MEMORY_AUTO_INDEX", "1") == "1"

PROJECT_MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
TASK_DB.parent.mkdir(parents=True, exist_ok=True)



SOURCE_ARCHIVE_DB = Path(os.getenv("SOURCE_ARCHIVE_DB", "data/source_archive.sqlite")).expanduser()
HYBRID_RAG_KEYWORD_WEIGHT = float(os.getenv("HYBRID_RAG_KEYWORD_WEIGHT", "0.35"))
HYBRID_RAG_VECTOR_WEIGHT = float(os.getenv("HYBRID_RAG_VECTOR_WEIGHT", "0.65"))
AUTOPILOT_MAX_STEPS = int(os.getenv("AUTOPILOT_MAX_STEPS", "8"))
AUTOPILOT_BUILD_EVERY_STEP = os.getenv("AUTOPILOT_BUILD_EVERY_STEP", "1") == "1"
STATUS_CHECK_TIMEOUT = int(os.getenv("STATUS_CHECK_TIMEOUT", "8"))
TOOLCHAIN_CHECK_TIMEOUT = int(os.getenv("TOOLCHAIN_CHECK_TIMEOUT", "8"))

SOURCE_ARCHIVE_DB.parent.mkdir(parents=True, exist_ok=True)



SANDBOX_DIR = Path(os.getenv("SANDBOX_DIR", "sandbox_runs")).expanduser()
SANDBOX_TIMEOUT = int(os.getenv("SANDBOX_TIMEOUT", "180"))
SANDBOX_BLOCK_NETWORK = os.getenv("SANDBOX_BLOCK_NETWORK", "0") == "1"
MODEL_MANAGER_PROFILE = os.getenv("MODEL_MANAGER_PROFILE", "ultra")
ORANGE_CORE_ROTATION = os.getenv("ORANGE_CORE_ROTATION", "1") == "1"

SANDBOX_DIR.mkdir(parents=True, exist_ok=True)



CRASH_LOG_DIR = Path(os.getenv("CRASH_LOG_DIR", "logs")).expanduser()
CRASH_RESTART_DELAY = int(os.getenv("CRASH_RESTART_DELAY", "5"))
WINDOWS_AGENT_SCREENSHOT_DIR = Path(os.getenv("WINDOWS_AGENT_SCREENSHOT_DIR", "data/screenshots")).expanduser()
OCR_LANGUAGE = os.getenv("OCR_LANGUAGE", "deu+eng")
PROJECT_BACKUP_DIR = Path(os.getenv("PROJECT_BACKUP_DIR", "project_backups")).expanduser()
AUTOPILOT_LOOP_MAX_ROUNDS = int(os.getenv("AUTOPILOT_LOOP_MAX_ROUNDS", "5"))
AUTOPILOT_LOOP_REQUIRE_TEST_PASS = os.getenv("AUTOPILOT_LOOP_REQUIRE_TEST_PASS", "1") == "1"

CRASH_LOG_DIR.mkdir(parents=True, exist_ok=True)
WINDOWS_AGENT_SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
PROJECT_BACKUP_DIR.mkdir(parents=True, exist_ok=True)



VIDEO_OUTPUT_DIR = Path(os.getenv("VIDEO_OUTPUT_DIR", "Jarvis_Projects/ki_videos")).expanduser()
VIDEO_DEFAULT_SECONDS = int(os.getenv("VIDEO_DEFAULT_SECONDS", "4"))
VIDEO_DEFAULT_FPS = int(os.getenv("VIDEO_DEFAULT_FPS", "16"))
VIDEO_DEFAULT_WIDTH = int(os.getenv("VIDEO_DEFAULT_WIDTH", "1024"))
VIDEO_DEFAULT_HEIGHT = int(os.getenv("VIDEO_DEFAULT_HEIGHT", "576"))
VIDEO_TARGET_WIDTH = int(os.getenv("VIDEO_TARGET_WIDTH", "3840"))
VIDEO_TARGET_HEIGHT = int(os.getenv("VIDEO_TARGET_HEIGHT", "2160"))
VIDEO_ENABLE_AUDIO = os.getenv("VIDEO_ENABLE_AUDIO", "1") == "1"
VIDEO_ENABLE_SPEECH = os.getenv("VIDEO_ENABLE_SPEECH", "1") == "1"
VIDEO_AUDIO_VOICE = os.getenv("VIDEO_AUDIO_VOICE", "Microsoft Michael")
VIDEO_AUDIO_MALE_VOICE = os.getenv("VIDEO_AUDIO_MALE_VOICE", VIDEO_AUDIO_VOICE)
VIDEO_AUDIO_FEMALE_VOICE = os.getenv("VIDEO_AUDIO_FEMALE_VOICE", "Microsoft Katja")
VIDEO_AUDIO_AUTO_GENDER = os.getenv("VIDEO_AUDIO_AUTO_GENDER", "1") == "1"
JARVIS_VIDEO_AUTO_WORKFLOW = os.getenv("JARVIS_VIDEO_AUTO_WORKFLOW", "1") == "1"
JARVIS_VIDEO_VRAM_GUARD = os.getenv("JARVIS_VIDEO_VRAM_GUARD", "1") == "1"
JARVIS_VIDEO_VRAM_GB = int(os.getenv("JARVIS_VIDEO_VRAM_GB", "16"))
JARVIS_STORAGE_FORCE_E = os.getenv("JARVIS_STORAGE_FORCE_E", "1") == "1"
VIDEO_MODE = os.getenv("VIDEO_MODE", "ComfyUI")
VIDEO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
