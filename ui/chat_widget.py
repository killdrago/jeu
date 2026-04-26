"""
Widget de chat principal.
- Affiche les messages avec syntaxe colorée
- Gère le streaming token par token
- Détecte les blocs de code dans la réponse IA
- Émet un signal quand l'IA propose une modification de code
"""

import re
from typing import List, Dict, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QLabel, QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QTextCursor, QTextCharFormat, QColor, QFont,
    QKeyEvent, QTextBlockFormat
)

from ui.styles import *


class ChatWidget(QWidget):
    """Zone de chat complète avec streaming."""

    # Émis quand l'utilisateur envoie un message
    message_sent = pyqtSignal(str)

    # Émis quand l'IA propose du code modifiable
    code_modification_proposed = pyqtSignal(str)  # réponse complète IA

    # Demande d'arrêt du streaming
    stop_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: List[Dict[str, str]] = []
        self._input_history: List[str] = []
        self._input_history_idx = -1
        self._is_streaming = False
        self._current_stream_start = 0
        self._cursor_timer = QTimer()
        self._cursor_visible = True
        self._full_ai_response = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # En-tête
        header = QLabel("  ◈ TERMINAL IA — ADMIN CONSOLE")
        header.setStyleSheet(HEADER_STYLE)
        layout.addWidget(header)

        # Zone d'affichage des messages
        self.display = QTextEdit()
        self.display.setReadOnly(True)
        self.display.setStyleSheet(f"""
            QTextEdit {{
                background: {C_BG};
                color: {C_WHITE};
                border: none;
                border-bottom: 1px solid {C_GRAY};
                padding: 10px;
                font-family: {FONT_MONO};
                font-size: 13px;
                line-height: 1.5;
            }}
        """)
        layout.addWidget(self.display, stretch=1)

        # Zone d'input
        input_frame = QFrame()
        input_frame.setStyleSheet(f"background: {C_BG2}; border-top: 1px solid {C_GRAY};")
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(8, 8, 8, 8)
        input_layout.setSpacing(6)

        # Ligne du haut: prompt + input
        top_row = QHBoxLayout()

        prompt_label = QLabel("▶")
        prompt_label.setStyleSheet(f"color: {C_GREEN}; font-size: 16px; padding-right: 6px;")
        top_row.addWidget(prompt_label)

        self.input_box = QTextEdit()
        self.input_box.setMaximumHeight(100)
        self.input_box.setMinimumHeight(40)
        self.input_box.setPlaceholderText(
            "Pose ta question… (Enter = envoyer, Shift+Enter = nouvelle ligne)"
        )
        self.input_box.setStyleSheet(f"""
            QTextEdit {{
                background: {C_BG};
                color: {C_GREEN};
                border: 1px solid {C_GREEN_DIM};
                border-radius: 4px;
                padding: 6px 10px;
                font-family: {FONT_MONO};
                font-size: 13px;
            }}
            QTextEdit:focus {{
                border-color: {C_GREEN};
            }}
        """)
        self.input_box.installEventFilter(self)
        top_row.addWidget(self.input_box, stretch=1)

        input_layout.addLayout(top_row)

        # Ligne du bas: boutons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.send_btn = QPushButton("▶  ENVOYER")
        self.send_btn.setStyleSheet(BUTTON_PRIMARY)
        self.send_btn.clicked.connect(self._send_message)
        btn_row.addWidget(self.send_btn)

        self.stop_btn = QPushButton("■  STOP")
        self.stop_btn.setStyleSheet(BUTTON_DANGER)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_requested)
        btn_row.addWidget(self.stop_btn)

        self.clear_btn = QPushButton("⌫  EFFACER")
        self.clear_btn.setStyleSheet(BUTTON_STYLE)
        self.clear_btn.clicked.connect(self._clear_chat)
        btn_row.addWidget(self.clear_btn)

        btn_row.addStretch()

        self.char_count = QLabel("0 car.")
        self.char_count.setStyleSheet(f"color: {C_GRAY}; font-size: 11px;")
        btn_row.addWidget(self.char_count)

        input_layout.addLayout(btn_row)
        layout.addWidget(input_frame)

        # Connecte le compteur
        self.input_box.textChanged.connect(self._update_char_count)

        # Timer curseur clignotant
        self._cursor_timer.timeout.connect(self._blink_cursor)
        self._cursor_timer.start(500)

        # Message de bienvenue
        self._show_welcome()

    # ─────────────────────────────────────────────
    # Messages d'affichage
    # ─────────────────────────────────────────────

    def _show_welcome(self):
        lines = [
            ("▓▓▓  ADMIN CONSOLE — IA LOCALE  ▓▓▓\n", C_GREEN, True),
            (f"{'─' * 45}\n", C_GRAY, False),
            ("Commandes spéciales:\n", C_YELLOW, False),
            ("  /modifier <fichier>  — Demande à l'IA de modifier un fichier\n", C_WHITE, False),
            ("  /fichiers            — Liste les fichiers de l'app\n", C_WHITE, False),
            ("  /snapshot            — Crée un snapshot Git maintenant\n", C_WHITE, False),
            ("  /historique          — Affiche l'historique des snapshots\n", C_WHITE, False),
            ("  /aide                — Aide complète\n", C_WHITE, False),
            (f"{'─' * 45}\n\n", C_GRAY, False),
        ]
        for text, color, bold in lines:
            self._append_text(text, color, bold)

    def _append_text(self, text: str, color: str = C_WHITE,
                     bold: bool = False, italic: bool = False):
        """Ajoute du texte formaté dans la zone d'affichage."""
        cursor = self.display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        if italic:
            fmt.setFontItalic(True)
        cursor.setCharFormat(fmt)
        cursor.insertText(text)
        self.display.setTextCursor(cursor)
        self.display.ensureCursorVisible()

    def _append_separator(self):
        self._append_text("─" * 50 + "\n", C_GRAY)

    def add_user_message(self, text: str):
        """Ajoute un message utilisateur."""
        self._append_text("\n┌─ VOUS ──────────────────────────────\n", C_BLUE, bold=True)
        self._append_text(f"│ {text}\n", C_BLUE)
        self._append_text("└" + "─" * 40 + "\n\n", C_BLUE)

    def start_ai_response(self):
        """Commence une réponse IA (mode streaming)."""
        self._is_streaming = True
        self._full_ai_response = ""
        self._append_text("┌─ IA ────────────────────────────────\n", C_GREEN, bold=True)
        self._append_text("│ ", C_GREEN)
        self._current_stream_start = self.display.textCursor().position()
        self.send_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def append_token(self, token: str):
        """Ajoute un token au streaming en cours."""
        self._full_ai_response += token
        # Remplace les \n par des "\n│ " pour l'alignement
        formatted = token.replace("\n", "\n│ ")
        self._append_text(formatted, C_GREEN)

    def finish_ai_response(self):
        """Termine la réponse IA."""
        self._is_streaming = False
        self._append_text("\n└" + "─" * 40 + "\n\n", C_GREEN)
        self.send_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        # Détecte si la réponse contient des blocs de code modifiables
        if self._contains_code_modification(self._full_ai_response):
            self._append_text(
                "  🔧 L'IA propose une modification de code.\n"
                "  → Voir onglet [MODIFICATION] pour valider ou refuser.\n\n",
                C_YELLOW, bold=True
            )
            self.code_modification_proposed.emit(self._full_ai_response)

    def _contains_code_modification(self, text: str) -> bool:
        """Détecte si la réponse contient du code à appliquer."""
        # Cherche des blocs ```python ... ``` avec un nom de fichier
        has_file_block = bool(re.search(
            r"##\s*FILE:\s*[\w/\\.\-]+",
            text, re.IGNORECASE
        ))
        has_named_code = bool(re.search(
            r"```\w+\s+filename:\s*[\w/\\.\-]+",
            text, re.IGNORECASE
        ))
        return has_file_block or has_named_code

    def show_error(self, message: str):
        """Affiche un message d'erreur."""
        self._is_streaming = False
        self._append_text(f"\n❌ ERREUR: {message}\n\n", C_RED, bold=True)
        self.send_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def show_system(self, message: str, color: str = C_YELLOW):
        """Affiche un message système."""
        self._append_text(f"⚙ {message}\n", color)

    # ─────────────────────────────────────────────
    # Input
    # ─────────────────────────────────────────────

    def eventFilter(self, obj, event):
        if obj is self.input_box and isinstance(event, QKeyEvent):
            # Enter = envoyer
            if (event.key() == Qt.Key.Key_Return and
                    not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier)):
                self._send_message()
                return True
            # Flèche haut = historique précédent
            if event.key() == Qt.Key.Key_Up:
                self._navigate_history(-1)
                return True
            # Flèche bas = historique suivant
            if event.key() == Qt.Key.Key_Down:
                self._navigate_history(1)
                return True
        return super().eventFilter(obj, event)

    def _send_message(self):
        text = self.input_box.toPlainText().strip()
        if not text or self._is_streaming:
            return

        # Sauvegarde dans l'historique
        if text not in self._input_history:
            self._input_history.append(text)
        self._input_history_idx = len(self._input_history)

        self.input_box.clear()
        self._history.append({"role": "user", "content": text})
        self.add_user_message(text)
        self.message_sent.emit(text)

    def _navigate_history(self, direction: int):
        if not self._input_history:
            return
        self._input_history_idx = max(
            0,
            min(len(self._input_history) - 1,
                self._input_history_idx + direction)
        )
        self.input_box.setPlainText(
            self._input_history[self._input_history_idx]
        )

    def _clear_chat(self):
        self.display.clear()
        self._history.clear()
        self._show_welcome()

    def _update_char_count(self):
        count = len(self.input_box.toPlainText())
        self.char_count.setText(f"{count} car.")

    def _blink_cursor(self):
        """Curseur clignotant dans la zone de saisie."""
        pass  # Qt gère ça nativement

    # ─────────────────────────────────────────────
    # Accesseurs
    # ─────────────────────────────────────────────

    def get_history(self) -> List[Dict[str, str]]:
        return self._history.copy()

    def add_to_history(self, role: str, content: str):
        self._history.append({"role": role, "content": content})

    def set_input_enabled(self, enabled: bool):
        self.input_box.setEnabled(enabled)
        self.send_btn.setEnabled(enabled and not self._is_streaming)
