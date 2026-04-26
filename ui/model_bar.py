"""
=======================================================
  ADMIN CONSOLE IA — Barre de statut du modèle (haut)
=======================================================
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton,
    QInputDialog, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont


STATUS_COLORS = {
    "none":    "#52525b",
    "loading": "#eab308",
    "ready":   "#22c55e",
    "error":   "#ef4444",
}

DOT_COLORS = {
    "none":    "#3f3f46",
    "loading": "#eab308",
    "ready":   "#22c55e",
    "error":   "#ef4444",
}


class ModelBar(QWidget):
    auto_detect_requested = pyqtSignal()
    manual_model_set = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setFixedHeight(38)
        self.setStyleSheet("""
            QWidget {
                background: #09090b;
                border-bottom: 1px solid #27272a;
            }
            QPushButton {
                background: transparent;
                color: #52525b;
                border: 1px solid #27272a;
                border-radius: 3px;
                padding: 2px 8px;
                font-family: Consolas, monospace;
                font-size: 11px;
            }
            QPushButton:hover {
                color: #d4d4d8;
                border-color: #52525b;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(10)

        # Indicateur LED
        self.dot = QLabel("●")
        self.dot.setFont(QFont("Consolas", 10))
        self.dot.setStyleSheet("color: #3f3f46; border: none;")
        layout.addWidget(self.dot)

        # Texte statut
        self.status_label = QLabel("Aucun modèle")
        self.status_label.setFont(QFont("Consolas", 10))
        self.status_label.setStyleSheet("color: #52525b; border: none;")
        layout.addWidget(self.status_label)

        # Séparateur
        sep = QLabel("│")
        sep.setStyleSheet("color: #27272a; border: none;")
        sep.setFont(QFont("Consolas", 10))
        layout.addWidget(sep)

        # Nom du modèle
        self.model_label = QLabel("")
        self.model_label.setFont(QFont("Consolas", 10))
        self.model_label.setStyleSheet("color: #a1a1aa; border: none;")
        layout.addWidget(self.model_label)

        layout.addStretch()

        # Titre central
        title = QLabel("⬡  ADMIN CONSOLE — IA LOCALE")
        title.setFont(QFont("Consolas", 10))
        title.setStyleSheet("color: #3f3f46; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        layout.addStretch()

        # Bouton AUTO
        self.btn_auto = QPushButton("[AUTO]")
        self.btn_auto.setToolTip("Détecter automatiquement le modèle via Ollama")
        self.btn_auto.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_auto.clicked.connect(self.auto_detect_requested.emit)
        layout.addWidget(self.btn_auto)

        # Bouton MANUEL
        self.btn_manual = QPushButton("[MANUEL]")
        self.btn_manual.setToolTip("Saisir manuellement le nom du modèle")
        self.btn_manual.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_manual.clicked.connect(self._ask_manual)
        layout.addWidget(self.btn_manual)

    def set_status(self, status: str, text: str):
        color = STATUS_COLORS.get(status, "#52525b")
        dot_color = DOT_COLORS.get(status, "#3f3f46")
        self.dot.setStyleSheet(f"color: {dot_color}; border: none;")
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; border: none;")

    def set_model(self, name: str, size: str = ""):
        display = name
        if size:
            display += f"  ({size})"
        self.model_label.setText(display)

    def _ask_manual(self):
        name, ok = QInputDialog.getText(
            self,
            "Modèle manuel",
            "Entrez le nom exact du modèle Ollama\n(ex: llama3.2, mistral, deepseek-r1:7b) :",
            QLineEdit.EchoMode.Normal,
            ""
        )
        if ok and name.strip():
            self.set_model(name.strip())
            self.manual_model_set.emit(name.strip())
