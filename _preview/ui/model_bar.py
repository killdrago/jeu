"""
Barre de sélection du modèle IA — détection auto + saisie manuelle.
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QStackedWidget, QFrame
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QColor

from ui.styles import *
from core.model_detector import ModelDetector


class ModelBar(QWidget):
    """Barre de sélection du modèle en haut de l'interface."""

    model_changed = pyqtSignal(str)
    status_updated = pyqtSignal(str, str)  # message, couleur

    def __init__(self, detector: ModelDetector, last_model: str = "", parent=None):
        super().__init__(parent)
        self.detector = detector
        self._current_model = last_model
        self._models: list = []
        self._setup_ui()

        # Détection auto au démarrage après 500ms
        QTimer.singleShot(500, self._auto_detect)

    def _setup_ui(self):
        self.setStyleSheet(f"""
            QWidget {{
                background: {C_BG2};
                border-bottom: 1px solid {C_GRAY};
            }}
        """)
        self.setFixedHeight(48)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        # Icône
        icon = QLabel("⬡")
        icon.setStyleSheet(f"color: {C_GREEN}; font-size: 18px; background: none; border: none;")
        layout.addWidget(icon)

        # Label
        lbl = QLabel("MODÈLE:")
        lbl.setStyleSheet(f"color: {C_GREEN_DIM}; font-size: 11px; font-weight: bold; letter-spacing: 1px; background: none; border: none;")
        layout.addWidget(lbl)

        # Combo modèles (mode auto)
        self.combo = QComboBox()
        self.combo.setStyleSheet(COMBO_STYLE + "QComboBox { background: #0f0f0f; min-width: 220px; }")
        self.combo.currentTextChanged.connect(self._on_combo_changed)
        layout.addWidget(self.combo)

        # Input manuel
        self.manual_input = QLineEdit()
        self.manual_input.setPlaceholderText("ex: llama3.2, mistral, deepseek-r1:7b")
        self.manual_input.setStyleSheet(INPUT_STYLE + "QLineEdit { min-width: 220px; background: #0f0f0f; }")
        self.manual_input.hide()
        self.manual_input.returnPressed.connect(self._on_manual_confirm)
        layout.addWidget(self.manual_input)

        # Bouton AUTO
        self.btn_auto = QPushButton("◎ AUTO")
        self.btn_auto.setCheckable(True)
        self.btn_auto.setChecked(True)
        self.btn_auto.setStyleSheet(BUTTON_PRIMARY + "QPushButton { padding: 3px 10px; font-size: 11px; }")
        self.btn_auto.clicked.connect(self._toggle_mode)
        layout.addWidget(self.btn_auto)

        # Bouton MANUEL
        self.btn_manual = QPushButton("✎ MANUEL")
        self.btn_manual.setCheckable(True)
        self.btn_manual.setStyleSheet(BUTTON_STYLE + "QPushButton { padding: 3px 10px; font-size: 11px; }")
        self.btn_manual.clicked.connect(self._toggle_mode)
        layout.addWidget(self.btn_manual)

        # Bouton Rafraîchir
        self.btn_refresh = QPushButton("↺")
        self.btn_refresh.setToolTip("Rafraîchir la liste des modèles")
        self.btn_refresh.setStyleSheet(BUTTON_STYLE + "QPushButton { padding: 3px 8px; font-size: 14px; }")
        self.btn_refresh.clicked.connect(self._auto_detect)
        layout.addWidget(self.btn_refresh)

        layout.addStretch()

        # Indicateur de statut
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(f"color: {C_GRAY}; font-size: 16px; background: none; border: none;")
        layout.addWidget(self.status_dot)

        self.status_label = QLabel("En attente...")
        self.status_label.setStyleSheet(f"color: {C_GRAY}; font-size: 11px; background: none; border: none;")
        layout.addWidget(self.status_label)

    def _auto_detect(self):
        """Détecte automatiquement les modèles disponibles."""
        self._set_status("Détection...", C_YELLOW)
        self.btn_refresh.setEnabled(False)

        # Vérification Ollama
        if not self.detector.is_ollama_running():
            self._set_status("Ollama non détecté", C_RED)
            self.btn_refresh.setEnabled(True)
            self.status_updated.emit(
                "⚠️ Ollama n'est pas lancé. Lance: ollama serve",
                C_RED
            )
            return

        models = self.detector.detect_ollama_models()
        self.btn_refresh.setEnabled(True)

        if not models:
            self._set_status("Aucun modèle", C_ORANGE)
            self.status_updated.emit(
                "Aucun modèle trouvé. Lance: ollama pull llama3.2",
                C_ORANGE
            )
            return

        self._models = models
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItems(models)

        # Restaure le dernier modèle utilisé
        if self._current_model in models:
            self.combo.setCurrentText(self._current_model)
        else:
            self._current_model = models[0]
            self.combo.setCurrentIndex(0)

        self.combo.blockSignals(False)
        self._set_status(f"OK — {len(models)} modèle(s)", C_GREEN)
        self.model_changed.emit(self._current_model)

    def _toggle_mode(self):
        """Bascule entre mode auto et manuel."""
        sender = self.sender()
        if sender is self.btn_auto:
            self.btn_auto.setChecked(True)
            self.btn_manual.setChecked(False)
            self.combo.show()
            self.manual_input.hide()
        else:
            self.btn_auto.setChecked(False)
            self.btn_manual.setChecked(True)
            self.combo.hide()
            self.manual_input.show()
            self.manual_input.setFocus()
            if self._current_model:
                self.manual_input.setText(self._current_model)

    def _on_combo_changed(self, model: str):
        if model and model != self._current_model:
            self._current_model = model
            self.model_changed.emit(model)

    def _on_manual_confirm(self):
        model = self.manual_input.text().strip()
        if model and model != self._current_model:
            self._current_model = model
            self._set_status(f"Manuel: {model}", C_BLUE)
            self.model_changed.emit(model)

    def _set_status(self, text: str, color: str):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {color}; font-size: 11px; background: none; border: none;"
        )
        self.status_dot.setStyleSheet(
            f"color: {color}; font-size: 16px; background: none; border: none;"
        )

    def get_current_model(self) -> str:
        return self._current_model
