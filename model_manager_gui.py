import sys
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit, QHBoxLayout

from skills.model_manager import ModelManager


class Worker(QThread):
    done = Signal(str)

    def __init__(self, fn, *args):
        super().__init__()
        self.fn = fn
        self.args = args

    def run(self):
        try:
            self.done.emit(self.fn(*self.args))
        except Exception as e:
            self.done.emit(f"Fehler: {e}")


class ModelManagerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.mm = ModelManager()
        self.setWindowTitle("Orange Jarvis - Modell Manager")
        self.resize(760, 520)

        layout = QVBoxLayout(self)
        title = QLabel("ORANGE JARVIS MODELL MANAGER")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:22px;font-weight:bold;color:#ff8c00;")
        layout.addWidget(title)

        row = QHBoxLayout()
        for name in ["ultra", "agent", "strong"]:
            b = QPushButton(name.upper())
            b.setMinimumHeight(44)
            b.clicked.connect(lambda checked=False, n=name: self.set_profile(n))
            row.addWidget(b)
        layout.addLayout(row)

        row2 = QHBoxLayout()
        for name in ["ultra", "agent", "strong"]:
            b = QPushButton("Modelle laden: " + name.upper())
            b.clicked.connect(lambda checked=False, n=name: self.pull(n))
            row2.addWidget(b)
        layout.addLayout(row2)

        self.out = QTextEdit()
        self.out.setReadOnly(True)
        self.out.setStyleSheet("background:#101010;color:#ffb347;font-family:Consolas;")
        layout.addWidget(self.out)

        list_btn = QPushButton("Ollama Modelle anzeigen")
        list_btn.clicked.connect(self.list_models)
        layout.addWidget(list_btn)

        self.out.setText(self.mm.list_profiles())

    def run_worker(self, fn, *args):
        self.worker = Worker(fn, *args)
        self.worker.done.connect(self.out.setText)
        self.worker.start()

    def set_profile(self, name):
        self.out.setText(self.mm.set_profile(name))

    def pull(self, name):
        self.out.setText("Lade Modelle. Das kann sehr lange dauern...")
        self.run_worker(self.mm.pull_profile_models, name)

    def list_models(self):
        self.run_worker(self.mm.ollama_list)


app = QApplication(sys.argv)
w = ModelManagerWindow()
w.show()
sys.exit(app.exec())
