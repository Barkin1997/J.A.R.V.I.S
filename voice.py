import json
import os
import subprocess
import tempfile
import winsound
import numpy as np
import pyttsx3
import sounddevice as sd
import threading
import queue
import time
from vosk import Model, KaldiRecognizer
from config import RECORD_SECONDS, VOSK_MODEL_DIR, VOICE_RATE, VOICE_VOLUME

MALE_VOICE_KEYS = [
    "michael",
    "stefan",
    "david",
    "mark",
    "george",
    "conrad",
    "killian",
    "florian",
    "male",
    "mann",
    "maennlich",
    "männlich",
]
PREFERRED_ONECORE_VOICE = "Microsoft Michael"


class VoiceSystem:
    def __init__(self):
        self.tts = None
        self.input_device = self._select_input_device()
        self.sample_rate = self._device_sample_rate(self.input_device)

        # Vosk Model lazy loading
        self.model = None
        if VOSK_MODEL_DIR.exists():
            try:
                self.model = Model(str(VOSK_MODEL_DIR))
            except Exception:
                self.model = None

        # Recognizer caching (lazy init)
        self._recognizer = None

        # Sprachausgabe-Warteschlange und Worker
        self._speak_queue = queue.Queue()
        self._speak_stop_event = threading.Event()
        self._speak_thread = threading.Thread(target=self._speak_worker, daemon=True)
        self._speak_thread.start()

    def _init_tts_engine(self):
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", VOICE_RATE)
            engine.setProperty("volume", VOICE_VOLUME)
            self._select_male_voice(engine)
            return engine
        except Exception:
            return None

    def _select_male_voice(self, engine=None):
        engine = engine or self.tts
        if engine is None:
            return
        try:
            voices = engine.getProperty("voices")
            keys = ["male", "david", "mark", "george", "stefan", "männlich"]
            keys = MALE_VOICE_KEYS
            for v in voices:
                label = f"{getattr(v, 'name', '')} {getattr(v, 'id', '')}".lower()
                if any(k in label for k in keys):
                    engine.setProperty("voice", v.id)
                    break
        except Exception:
            pass

    def _select_input_device(self):
        try:
            preferred = os.getenv("JARVIS_MIC_NAME", "").lower().strip()
            fallback_names = [preferred, "mic in (elgato wave:3)", "mic in", "wave link microphonefx", "mikrofon", "microphone"]
            devices = sd.query_devices()
            for needle in fallback_names:
                if not needle:
                    continue
                for index, dev in enumerate(devices):
                    if int(dev.get("max_input_channels", 0)) <= 0:
                        continue
                    if needle in str(dev.get("name", "")).lower():
                        return index
        except Exception:
            pass
        return None

    def _device_sample_rate(self, device):
        try:
            if device is not None:
                return int(sd.query_devices(device).get("default_samplerate") or 16000)
        except Exception:
            pass
        return 16000

    def stop(self):
        # Stop Sprachausgabe-Thread
        self._speak_stop_event.set()
        try:
            self.tts.stop()
        except Exception:
            pass
        # Warteschlange leeren, um blockierende Aufrufe zu vermeiden
        while not self._speak_queue.empty():
            try:
                self._speak_queue.get_nowait()
            except queue.Empty:
                break

    def speak(self, text: str):
        text = (text or "").strip()
        if not text:
            return
        if len(text) > 1100:
            text = text[:1100] + "..."
        # In Warteschlange legen – Ausführung erfolgt im Hintergrundthread
        self._speak_queue.put_nowait(("speak", text))

    def _speak_worker(self):
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception:
            pass
        self.tts = self._init_tts_engine()

        while not self._speak_stop_event.is_set():
            try:
                item = self._speak_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            action, payload = item
            if action == "speak":
                text = payload
                # Versuche erst OneCore (wenn verfügbar), dann pyttsx3, dann Fallback
                if not self._speak_onecore_michael(text):
                    try:
                        self.tts.say(text)
                        self.tts.runAndWait()
                    except Exception as e:
                        # Fallback: PowerShell-TTS auf Windows
                        self._fallback_speak_windows(text)
            elif action == "stop":
                break

        try:
            import pythoncom
            pythoncom.CoUninitialize()
        except Exception:
            pass

    def _fallback_speak_windows(self, text: str):
        try:
            script = f'''
Add-Type -AssemblyName System.Speech;
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer;
$synth.Rate = 0;
$synth.Volume = 100;
$synth.Speak("{text.replace('"', '""')}");
'''
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True,
                timeout=30,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            pass

    def _speak_onecore_michael(self, text: str) -> bool:
        wav_path = ""
        try:
            fd, wav_path = tempfile.mkstemp(prefix="jarvis_michael_", suffix=".wav")
            os.close(fd)
            script = r'''
$ErrorActionPreference = 'Stop'
$out = $env:JARVIS_TTS_OUT
$text = $env:JARVIS_TTS_TEXT
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime] | Out-Null
[Windows.Media.SpeechSynthesis.SpeechSynthesisStream, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime] | Out-Null
$synth = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::new()
$voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.DisplayName -eq 'Microsoft Michael' } | Select-Object -First 1
if($null -eq $voice){ throw 'Microsoft Michael voice not found' }
$synth.Voice = $voice
$op = $synth.SynthesizeTextToStreamAsync($text)
$method = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethodDefinition -and $_.GetParameters().Count -eq 1 } | Select-Object -First 1
$task = $method.MakeGenericMethod([Windows.Media.SpeechSynthesis.SpeechSynthesisStream]).Invoke($null, @($op))
$stream = $task.GetAwaiter().GetResult()
$inStream = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($stream)
$file = [System.IO.File]::Create($out)
try {
  $inStream.CopyTo($file)
} finally {
  $file.Close()
  $inStream.Close()
  $stream.Dispose()
  $synth.Dispose()
}
'''
            env = os.environ.copy()
            env["JARVIS_TTS_TEXT"] = text
            env["JARVIS_TTS_OUT"] = wav_path
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode != 0 or not os.path.exists(wav_path) or os.path.getsize(wav_path) < 1000:
                return False
            winsound.PlaySound(wav_path, winsound.SND_FILENAME)
            return True
        except Exception:
            return False
        finally:
            if wav_path:
                try:
                    os.remove(wav_path)
                except Exception:
                    pass

    def _get_recognizer(self):
        # Lazy-Initialisierung des Recognizers
        if self._recognizer is None:
            if self.model is None:
                return None
            try:
                self._recognizer = KaldiRecognizer(self.model, self.sample_rate)
            except Exception:
                self._recognizer = None
        return self._recognizer

    def listen_once(self, timeout: float = 15.0) -> str:
        # Maximal 3 Versuche bei Fehlern
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                if self.model is None:
                    return "Vosk-Modell fehlt. Starte download_vosk_de.bat."

                # Audio aufnehmen mit Timeout
                audio_data = sd.rec(
                    int(RECORD_SECONDS * self.sample_rate),
                    samplerate=self.sample_rate,
                    channels=1,
                    dtype=np.int16,
                    device=self.input_device,
                )
                sd.wait()

                rec = self._get_recognizer()
                if rec is None:
                    return "Vosk-Recognizer konnte nicht initialisiert werden."

                rec.AcceptWaveform(audio_data.tobytes())
                result = json.loads(rec.FinalResult())
                text = result.get("text", "").strip()

                # Optional: Wenn nichts erkannt wurde, nochmal versuchen
                if not text and attempt < max_retries:
                    continue

                return text

            except sd.PortAudioError as e:
                # Mikrofonproblem – warten und neu probieren
                time.sleep(1.0)
                continue
            except Exception as e:
                # Andere Fehler – abhängig vom Typ ggf. neu versuchen
                if attempt < max_retries:
                    time.sleep(1.0)
                    continue
                else:
                    return f"Spracherkennung fehlgeschlagen nach {max_retries} Versuchen: {e}"

        return "Spracherkennung nach mehreren Fehlversuchen abgebrochen."

    def reset_recognizer(self):
        self._recognizer = None


_voice_system = None


def get_voice_system():
    global _voice_system
    if _voice_system is None:
        _voice_system = VoiceSystem()
    return _voice_system


def listen_once(timeout: float = 15.0) -> str:
    return get_voice_system().listen_once(timeout=timeout)


def speak_text(text: str):
    return get_voice_system().speak(text)
