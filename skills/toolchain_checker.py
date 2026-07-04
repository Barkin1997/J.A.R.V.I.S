import shutil
import subprocess

from config import TOOLCHAIN_CHECK_TIMEOUT


class ToolchainChecker:
    TOOLS = {
        "C++ g++": ("g++", "--version", "install_dev_tools_FULL.bat oder MinGW/MSYS2 installieren"),
        "C++ MSVC cl.exe": ("cl", "", "Visual Studio Build Tools + Desktop development with C++ aktivieren"),
        "CMake": ("cmake", "--version", "install_dev_tools_FULL.bat"),
        "Ninja": ("ninja", "--version", "install_dev_tools_FULL.bat"),
        "Python": ("python", "--version", "install_dev_tools_FULL.bat"),
        "Node": ("node", "--version", "install_dev_tools_FULL.bat"),
        "NPM": ("npm", "--version", "install_dev_tools_FULL.bat"),
        ".NET": ("dotnet", "--version", "install_dev_tools_FULL.bat"),
        "Java javac": ("javac", "-version", "install_dev_tools_FULL.bat"),
        "Rust Cargo": ("cargo", "--version", "install_dev_tools_FULL.bat"),
        "Go": ("go", "version", "install_dev_tools_FULL.bat"),
        "Git": ("git", "--version", "install_dev_tools_FULL.bat"),
    }

    def check(self) -> str:
        lines = ["Toolchain-Prüfung:"]
        for name, (exe, arg, fix) in self.TOOLS.items():
            if not shutil.which(exe):
                lines.append(f"- {name}: FEHLT → {fix}")
                continue
            try:
                result = subprocess.run(f"{exe} {arg}".strip(), shell=True, text=True, capture_output=True, timeout=TOOLCHAIN_CHECK_TIMEOUT)
                out = (result.stdout or result.stderr or "gefunden").splitlines()
                lines.append(f"- {name}: OK ({out[0][:100] if out else 'gefunden'})")
            except Exception:
                lines.append(f"- {name}: gefunden, Version nicht lesbar")
        return "\n".join(lines)
