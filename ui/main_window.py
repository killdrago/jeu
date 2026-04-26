"""
=======================================================
  ADMIN CONSOLE IA — Fenêtre principale
=======================================================
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStatusBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette

from ui.chat_widget import ChatWidget
from ui.model_bar import ModelBar
from core.model_detector import ModelDetector


BOOT_LINES = [
    "ADMIN CONSOLE v1.0 — Système IA local",
    "─────────────────────────────────────────",
    "› Initialisation du système...",
    "› Recherche du dossier ./model/ ...",
    "› Connexion à Ollama (localhost:11434)...",
    "› Utilisez [AUTO] pour détecter votre modèle",
    "  ou [MANUEL] pour entrer son nom.",
    "─────────────────────────────────────────",
    "",
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Admin Console — IA Locale")
        self.setMinimumSize(900, 650)
        self.resize(1100, 720)

        # Palette sombre
        self._apply_dark_theme()

        # Widget central
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Barre modèle (haut)
        self.model_bar = ModelBar()
        self.model_bar.auto_detect_requested.connect(self._auto_detect)
        self.model_bar.manual_model_set.connect(self._on_model_set)
        layout.addWidget(self.model_bar)

        # Zone chat
        self.chat_widget = ChatWidget()
        layout.addWidget(self.chat_widget)

        # Status bar
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("background:#0a0a0a; color:#52525b; font-family:Consolas,monospace; font-size:11px; border-top:1px solid #27272a;")
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ollama : localhost:11434  |  ↑↓ historique  |  Shift+Entrée = nouvelle ligne")

        # Animation de boot
        self._boot_index = 0
        self._boot_timer = QTimer()
        self._boot_timer.timeout.connect(self._boot_step)
        self._boot_timer.start(110)

    def _boot_step(self):
        if self._boot_index < len(BOOT_LINES):
            line = BOOT_LINES[self._boot_index]
            self.chat_widget.append_boot_line(line)
            self._boot_index += 1
        else:
            self._boot_timer.stop()
            # Lancement de la détection automatique
            self._auto_detect()

    def _auto_detect(self):
        self.model_bar.set_status("loading", "Détection...")
        detector = ModelDetector(parent=self)
        detector.model_found.connect(self._on_model_detected)
        detector.model_not_found.connect(self._on_no_model)
        detector.start()

    def _on_model_detected(self, name: str, size: str):
        self.model_bar.set_model(name, size)
        self.model_bar.set_status("ready", f"Prêt — {name}")
        self.chat_widget.set_model(name)
        self.chat_widget.append_system(f"✓ Modèle détecté automatiquement : {name}  ({size})")

    def _on_no_model(self, error: str):
        self.model_bar.set_status("error", error)
        self.chat_widget.append_system(f"⚠ {error}")
        self.chat_widget.append_system(
            "Assurez-vous qu'Ollama est lancé : ollama serve\n"
            "Puis importez votre modèle : ollama create mon-model -f ./model/Modelfile"
        )

    def _on_model_set(self, name: str):
        self.model_bar.set_status("ready", f"Prêt — {name}")
        self.chat_widget.set_model(name)
        self.chat_widget.append_system(f"✓ Modèle défini manuellement : {name}")

    def _apply_dark_theme(self):
        palette = QPalette()
        black = QColor("#000000")
        dark = QColor("#09090b")
        mid = QColor("#18181b")
        text = QColor("#d4d4d8")
        highlight = QColor("#16a34a")

        palette.setColor(QPalette.ColorRole.Window, dark)
        palette.setColor(QPalette.ColorRole.WindowText, text)
        palette.setColor(QPalette.ColorRole.Base, black)
        palette.setColor(QPalette.ColorRole.AlternateBase, mid)
        palette.setColor(QPalette.ColorRole.Text, text)
        palette.setColor(QPalette.ColorRole.Button, mid)
        palette.setColor(QPalette.ColorRole.ButtonText, text)
        palette.setColor(QPalette.ColorRole.Highlight, highlight)
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        self.setPalette(palette)
