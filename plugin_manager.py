import importlib.util
from pathlib import Path
from typing import List

from config import PROJECT_DIR


class PluginManager:
    def __init__(self, plugins_dir: str = "plugins"):
        self.plugins_dir = Path(plugins_dir)
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.plugins = []
        self.load_plugins()

    def load_plugins(self):
        self.plugins = []
        for file in self.plugins_dir.glob("*.py"):
            if file.name.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(file.stem, file)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if hasattr(mod, "can_handle") and hasattr(mod, "handle"):
                    self.plugins.append(mod)
            except Exception:
                continue

    def list_plugins(self) -> str:
        if not self.plugins:
            return "Keine Plugins geladen."
        names = []
        for p in self.plugins:
            names.append(getattr(p, "NAME", p.__name__))
        return "Plugins:\n" + "\n".join(f"- {n}" for n in names)

    def handle(self, command: str, context: dict) -> str:
        for plugin in self.plugins:
            try:
                if plugin.can_handle(command):
                    return plugin.handle(command, context)
            except Exception as e:
                return f"Plugin-Fehler in {getattr(plugin, 'NAME', plugin.__name__)}: {e}"
        return ""
