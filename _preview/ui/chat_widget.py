"""
Widget de chat principal (version mise à jour).
- Affiche les messages avec syntaxe colorée
- Gère le streaming token par token
- Détecte les blocs ## FILE: dans la réponse IA
- Masque le code brut dans le chat (il va dans le panneau droit)
- Émet un signal quand l'IA propose une modification de code

CHANGEMENTS v2.1:
- Méthode set_input() ajoutée (pour charger un fichier depuis FileBrowser)
- Méthode get_history() ajoutée
- Méthode add_error() ajoutée
- finish_ai_response() accepte la réponse complète
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
    QKeyEvent
)

from ui.styles import *


class ChatWidget(QWidget):
    """Zone de chat complète avec streaming."""

    # Émis quand l'utilisateur envoie un message
    message_sent = pyqtSignal(str)

    # Émis quand l'IA propose du code modifiable
    code_modification_proposed = pyqtSignal(str)   # réponse complète IA

    # Demande d'arrêt du streaming
    stop_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: List[Dict[str, str]] = []
        self._input_history: List[str] = []
        self._input_history_idx = -1
        self._is_streaming = False
        self._current_stream_start = 0
        self._full_ai_response = ""

        # Pour masquer les blocs de code pendant le streaming
        self._in_file_block = False
        self._file_block_buffer = ""
        self._pending_text = ""

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
        input_frame.setStyleSheet(
            f"background: {C_BG2}; border-top: 1px solid {C_GRAY};"
        )
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(8, 8, 8, 8)
        input_layout.setSpacing(6)

        # Ligne du haut: prompt + input
        top_row = QHBoxLayout()
        prompt_label = QLabel("▶")
        prompt_label.setStyleSheet(
            f"color: {C_GREEN}; font-size: 16px; padding-right: 6px;"
        )
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

        self.send_btn = QPushButton("▶ ENVOYER")
        self.send_btn.setStyleSheet(BUTTON_PRIMARY)
        self.send_btn.clicked.connect(self._send_message)
        btn_row.addWidget(self.send_btn)

        self.stop_btn = QPushButton("■ STOP")
        self.stop_btn.setStyleSheet(BUTTON_DANGER)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_requested)
        btn_row.addWidget(self.stop_btn)

        self.clear_btn = QPushButton("⌫ EFFACER")
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

        # Message de bienvenue
        self._show_welcome()

    # ─────────────────────────────────────────────
    # API publique
    # ─────────────────────────────────────────────

    def get_history(self) -> List[Dict[str, str]]:
        """Retourne l'historique de la conversation."""
        return list(self._history)

    def set_input(self, text: str):
        """Charge un texte dans l'input (depuis FileBrowser)."""
        self.input_box.setPlainText(text)
        self.input_box.setFocus()

    def add_error(self, error: str):
        """Affiche un message d'erreur dans le chat."""
        self._append_text(f"\n❌ ERREUR: {error}\n\n", C_RED, bold=True)

    def start_ai_response(self):
        """Commence une réponse IA (mode streaming)."""
        self._is_streaming = True
        self._full_ai_response = ""
        self._in_file_block = False
        self._file_block_buffer = ""
        self._pending_text = ""

        self._append_text(
            "┌─ IA ────────────────────────────────\n", C_GREEN, bold=True
        )
        self._append_text("│ ", C_GREEN)
        self._current_stream_start = self.display.textCursor().position()

        self.send_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def append_ai_token(self, token: str):
        """Ajoute un token de streaming en filtrant les blocs ## FILE:."""
        self._full_ai_response += token
        self._pending_text += token

        # Vérifie si on entre dans un bloc ## FILE:
        if not self._in_file_block:
            if "## FILE:" in self._pending_text:
                # On entre dans un bloc de code
                idx = self._pending_text.index("## FILE:")
                # Affiche le texte avant le bloc
                before = self._pending_text[:idx]
                if before:
                    self._append_text(before, C_WHITE)
                self._in_file_block = True
                self._file_block_buffer = self._pending_text[idx:]
                self._pending_text = ""
                # Affiche un indicateur discret
                self._append_text(
                    "\n[→ Code envoyé dans le panneau droit]\n", C_GRAY, italic=True
                )
            elif len(self._pending_text) > 100:
                # Flush le buffer si pas de bloc en vue
                self._append_text(self._pending_text, C_WHITE)
                self._pending_text = ""
        else:
            # On est dans un bloc, accumule dans le buffer
            self._file_block_buffer += token
            # Vérifie si le bloc est terminé (``` fermant)
            if self._file_block_buffer.count("```") >= 2:
                self._in_file_block = False
                self._file_block_buffer = ""
                self._pending_text = ""

    def finish_ai_response(self, full_response: str):
        """Termine la réponse IA."""
        # Flush le texte en attente (non-code)
        if self._pending_text and not self._in_file_block:
            self._append_text(self._pending_text, C_WHITE)
        self._pending_text = ""
        self._in_file_block = False

        self._full_ai_response = full_response
        self._is_streaming = False

        self._append_text(
            "\n└" + "─" * 40 + "\n\n", C_GREEN
        )

        self.send_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        # Ajoute à l'historique
        if full_response:
            self._history.append({
                "role": "assistant",
                "content": full_response
            })

    # ─────────────────────────────────────────────
    # Messages d'affichage
    # ─────────────────────────────────────────────

    def _show_welcome(self):
        lines = [
            ("▓▓▓ ADMIN CONSOLE — IA LOCALE ▓▓▓\n", C_GREEN, True),
            (f"{'─' * 45}\n", C_GRAY, False),
            ("Workflow modification:\n", C_YELLOW, True),
            ("  1. Demande une modif (ex: 'mets le fond en blanc')\n", C_WHITE, False),
            ("  2. L'IA décrit ici ce qu'elle fait\n", C_WHITE, False),
            ("  3. Le code → panneau DROIT (onglet '{ } Code')\n", C_WHITE, False),
            ("  4. Lignes modifiées surlignées en vert + gras\n", C_WHITE, False),
            ("  5. ▶ TESTER → lance l'app modifiée en sous-process\n", C_WHITE, False),
            ("  6. ✔ ACCEPTER → applique | ✘ REFUSER → rollback\n", C_WHITE, False),
            (f"{'─' * 45}\n\n", C_GRAY, False),
        ]
        for text, color, bold in lines:
            self._append_text(text, color, bold)

    def _append_text(
        self, text: str, color: str = C_WHITE,
        bold: bool = False, italic: bool = False
    ):
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

    def add_user_message(self, text: str):
        """Ajoute un message utilisateur."""
        self._append_text("\n┌─ VOUS ──────────────────────────────\n", C_BLUE, bold=True)
        self._append_text(f"│ {text}\n", C_BLUE)
        self._append_text("└" + "─" * 40 + "\n\n", C_BLUE)
        self._history.append({"role": "user", "content": text})

    def _send_message(self):
        text = self.input_box.toPlainText().strip()
        if not text or self._is_streaming:
            return
        self.input_box.clear()
        self.add_user_message(text)
        self.message_sent.emit(text)

    def _clear_chat(self):
        self.display.clear()
        self._history.clear()
        self._show_welcome()

    def _update_char_count(self):
        n = len(self.input_box.toPlainText())
        self.char_count.setText(f"{n} car.")

    def eventFilter(self, obj, event):
        """Intercepte Enter pour envoyer."""
        if obj is self.input_box and isinstance(event, QKeyEvent):
            if (event.key() == Qt.Key.Key_Return and
                    not event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self._send_message()
                return True
        return super().eventFilter(obj, event)
