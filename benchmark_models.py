import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from config import PROJECT_DIR, OLLAMA_AGENT_CODE_MODEL, OLLAMA_STRONG_CODE_MODEL, OLLAMA_BEAST_CODE_MODEL
from ollama_client import OllamaClient

client = OllamaClient()
models = []
for m in [OLLAMA_AGENT_CODE_MODEL, OLLAMA_STRONG_CODE_MODEL, OLLAMA_BEAST_CODE_MODEL]:
    if m and m not in models:
        models.append(m)

bench_dir = PROJECT_DIR / "benchmarks"
bench_dir.mkdir(parents=True, exist_ok=True)

task = """
Erstelle ein kleines C++20 Projekt.

Antworte NUR JSON:
{
 "files": [
   {"path":"main.cpp","content":"..."}
 ],
 "run":"g++ main.cpp -std=c++20 -O2 -Wall -Wextra -o bench.exe"
}

Programm:
- implementiert isPrime(int)
- testet 2,3,4,17,18,97
- gibt PASS aus, wenn alles stimmt
"""

def parse_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.I).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, flags=re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None

rows = []
for model in models:
    print("=" * 80)
    print("MODELL:", model)
    folder = bench_dir / re.sub(r"[^a-zA-Z0-9]+", "_", model)
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)

    start = time.time()
    raw = client.complete(task, model=model, system="Du bist ein Code-Benchmark-Agent. Nur JSON.", temperature=0.03)
    gen_sec = time.time() - start
    data = parse_json(raw)

    score = 0
    compile_log = ""
    run_log = ""

    if data:
        score += 1
        for f in data.get("files", []):
            p = folder / f.get("path", "main.cpp")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f.get("content", ""), encoding="utf-8")
        if shutil.which("g++") and (folder / "main.cpp").exists():
            cmd = "g++ main.cpp -std=c++20 -O2 -Wall -Wextra -o bench.exe"
            c = subprocess.run(cmd, cwd=str(folder), shell=True, text=True, capture_output=True, timeout=60)
            compile_log = c.stdout + c.stderr
            if c.returncode == 0:
                score += 2
                r = subprocess.run("bench.exe", cwd=str(folder), shell=True, text=True, capture_output=True, timeout=30)
                run_log = r.stdout + r.stderr
                if r.returncode == 0:
                    score += 1
                if "PASS" in run_log:
                    score += 2
        else:
            compile_log = "g++ nicht gefunden oder main.cpp fehlt."
    else:
        compile_log = "Kein JSON."

    rows.append((score, gen_sec, model, compile_log[:500], run_log[:500]))
    print("Score:", score)
    print("Zeit:", round(gen_sec, 2), "s")
    print("Compile:", compile_log[:500])
    print("Run:", run_log[:500])

print("\nERGEBNIS")
for score, sec, model, _, _ in sorted(rows, reverse=True):
    print(f"{model}: Score={score}, Zeit={sec:.2f}s")
