"""
=======================================================
  ADMIN CONSOLE IA — Zone de chat principale
=======================================================
"""

from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor, QColor

from core.ollama_worker import OllamaWorker


class ChatWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._model_name = ""
        self._history = []       # historique des commandes
        self._history_idx = -1
        self._worker = None
        self._current_ai_block = ""

        self._build_ui()

    # ─────────────────────────────────────────
    #  Construction de l'UI
    # ─────────────────────────────────────────
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Zone d'affichage des messages
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Consolas", 11))
        self.output.setStyleSheet("""
            QTextEdit {
                background: #000000;
                color: #d4d4d8;
                border: none;
                padding: 12px 16px;
                selection-background-color: #16a34a;
            }
            QScrollBar:vertical {
                background: #09090b;
                width: 6px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background: #27272a;
                border-radius: 3px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)
        layout.addWidget(self.output)

        # Barre de modèle actif (petit rappel au-dessus de l'input)
        self.model_hint = QLabel("Aucun modèle sélectionné")
        self.model_hint.setFont(QFont("Consolas", 10))
        self.model_hint.setStyleSheet("""
            background: #09090b;
            color: #3f3f46;
            padding: 3px 16px;
            border-top: 1px solid #18181b;
        """)
        layout.addWidget(self.model_hint)

        # Zone d'input
        input_container = QWidget()
        input_container.setStyleSheet("background: #09090b; border-top: 1px solid #27272a;")
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(12, 10, 12, 10)
        input_layout.setSpacing(8)

        # Prompt symbol
        prompt_sym = QLabel("›_")
        prompt_sym.setFont(QFont("Consolas", 13))
        prompt_sym.setStyleSheet("color: #16a34a; background: transparent; border: none;")
        prompt_sym.setAlignment(Qt.AlignmentFlag.AlignTop)
        prompt_sym.setFixedWidth(26)
        input_layout.addWidget(prompt_sym)

        # Champ de saisie
        self.input_box = _InputBox(self)
        self.input_box.submit_requested.connect(self._send)
        self.input_box.history_up.connect(self._history_up)
        self.input_box.history_down.connect(self._history_down)
        self.input_box.setFont(QFont("Consolas", 11))
        self.input_box.setStyleSheet("""
            QTextEdit {
                background: #18181b;
                color: #e4e4e7;
                border: 1px solid #27272a;
                border-radius: 4px;
                padding: 6px 10px;
                selection-background-color: #16a34a;
            }
            QTextEdit:focus {
                border-color: #15803d;
            }
        """)
        self.input_box.setFixedHeight(42)
        self.input_box.setPlaceholderText("Chargez un modèle puis tapez votre message…")
        input_layout.addWidget(self.input_box)

        # Bouton SEND / STOP
        self.btn_send = QPushButton("► SEND")
        self.btn_send.setFont(QFont("Consolas", 10))
        self.btn_send.setFixedSize(80, 40)
        self.btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_send.setStyleSheet("""
            QPushButton {
                background: #14532d;
                color: #4ade80;
                border: 1px solid #166534;
                border-radius: 4px;
            }
            QPushButton:hover { background: #166534; }
            QPushButton:disabled { background: #18181b; color: #3f3f46; border-color: #27272a; }
        """)
        self.btn_send.clicked.connect(self._send)
        self.btn_send.setEnabled(False)
        input_layout.addWidget(self.btn_send)

        layout.addWidget(input_container)

    # ─────────────────────────────────────────
    #  API publique
    # ─────────────────────────────────────────
    def set_model(self, name: str):
        self._model_name = name
        self.model_hint.setText(f"Modèle actif : {name}")
        self.model_hint.setStyleSheet("""
            background: #09090b;
            color: #22c55e;
            padding: 3px 16px;
            border-top: 1px solid #18181b;
        """)
        self.input_box.setPlaceholderText("Tapez votre message… (Entrée pour envoyer, Shift+Entrée = saut de ligne)")
        self.btn_send.setEnabled(True)

    def append_boot_line(self, line: str):
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = self.output.currentCharFormat()
        if "ADMIN CONSOLE" in line:
            fmt.setForeground(QColor("#22c55e"))
        elif line.startswith("─"):
            fmt.setForeground(QColor("#27272a"))
        elif line.startswith("›"):
            fmt.setForeground(QColor("#71717a"))
        else:
            fmt.setForeground(QColor("#52525b"))

        cursor.insertText(line + "\n", fmt)
        self._scroll_bottom()

    def append_system(self, text: str):
        self._append_colored(f"\n[SYS] {text}\n", "#eab308")

    def append_user(self, text: str):
        ts = datetime.now().strftime("%H:%M:%S")
        header = f"\n[{ts}] YOU\n"
        self._append_colored(header, "#60a5fa")
        self._append_colored(text + "\n", "#bfdbfe")

    def append_ai_start(self):
        ts = datetime.now().strftime("%H:%M:%S")
        header = f"\n[{ts}] AI\n"
        self._append_colored(header, "#4ade80")
        self._current_ai_block = ""

    def append_ai_chunk(self, chunk: str):
        self._current_ai_block += chunk
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = self.output.currentCharFormat()
        fmt.setForeground(QColor("#86efac"))
        cursor.insertText(chunk, fmt)
        self._scroll_bottom()

    def append_ai_end(self):
        self._append_colored("\n", "#86efac")
        self._current_ai_block = ""

    # ─────────────────────────────────────────
    #  Envoi du message
    # ─────────────────────────────────────────
    def _send(self):
        text = self.input_box.toPlainText().strip()
        if not text or not self._model_name:
            return

        # Historique
        self._history.insert(0, text)
        if len(self._history) > 50:
            self._history = self._history[:50]
        self._history_idx = -1

        self.input_box.clear()
        self.input_box.setFixedHeight(42)
        self.append_user(text)
        self._set_thinking(True)

        # Lancement dans un QThread
        self._worker = OllamaWorker(self._model_name, text)
        self._worker.token_received.connect(self._on_token)
        self._worker.finished.connect(self._on_done)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

        self.append_ai_start()

    def _on_token(self, chunk: str):
        self.append_ai_chunk(chunk)

    def _on_done(self):
        self.append_ai_end()
        self._set_thinking(False)

    def _on_error(self, msg: str):
        self.append_ai_end()
        self.append_system(f"Erreur : {msg}")
        self._set_thinking(False)

    def _set_thinking(self, thinking: bool):
        if thinking:
            self.btn_send.setText("■ STOP")
            self.btn_send.setStyleSheet("""
                QPushButton {
                    background: #450a0a;
                    color: #f87171;
                    border: 1px solid #7f1d1d;
                    border-radius: 4px;
                }
                QPushButton:hover { background: #7f1d1d; }
            """)
            self.btn_send.clicked.disconnect()
            self.btn_send.clicked.connect(self._stop)
            self.input_box.setEnabled(False)
        else:
            self.btn_send.setText("► SEND")
            self.btn_send.setStyleSheet("""
                QPushButton {
                    background: #14532d;
                    color: #4ade80;
                    border: 1px solid #166534;
                    border-radius: 4px;
                }
                QPushButton:hover { background: #166534; }
                QPushButton:disabled { background: #18181b; color: #3f3f46; border-color: #27272a; }
            """)
            self.btn_send.clicked.disconnect()
            self.btn_send.clicked.connect(self._send)
            self.input_box.setEnabled(True)
            self.input_box.setFocus()

    def _stop(self):
        if self._worker:
            self._worker.stop()

    # ─────────────────────────────────────────
    #  Historique clavier ↑ ↓
    # ─────────────────────────────────────────
    def _history_up(self):
        if not self._history:
            return
        self._history_idx = min(self._history_idx + 1, len(self._history) - 1)
        self.input_box.setPlainText(self._history[self._history_idx])
        self._move_cursor_end()

    def _history_down(self):
        if self._history_idx <= 0:
            self._history_idx = -1
            self.input_box.clear()
            return
        self._history_idx -= 1
        self.input_box.setPlainText(self._history[self._history_idx])
        self._move_cursor_end()

    def _move_cursor_end(self):
        cursor = self.input_box.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.input_box.setTextCursor(cursor)

    # ─────────────────────────────────────────
    #  Helpers
    # ─────────────────────────────────────────
    def _append_colored(self, text: str, color: str):
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = self.output.currentCharFormat()
        fmt.setForeground(QColor(color))
        cursor.insertText(text, fmt)
        self._scroll_bottom()

    def _scroll_bottom(self):
        self.output.verticalScrollBar().setValue(
            self.output.verticalScrollBar().maximum()
        )


# ─────────────────────────────────────────
#  Widget input personnalisé (gestion touches)
# ─────────────────────────────────────────
class _InputBox(QTextEdit):
    submit_requested = pyqtSignal()
    history_up = pyqtSignal()
    history_down = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(False)

    def keyPressEvent(self, event):
        from PyQt6.QtCore import Qt
        key = event.key()
        mods = event.modifiers()

        # Entrée seule → envoyer
        if key == Qt.Key.Key_Return and not (mods & Qt.KeyboardModifier.ShiftModifier):
            self.submit_requested.emit()
            return

        # ↑ → historique précédent
        if key == Qt.Key.Key_Up and self.toPlainText().count("\n") == 0:
            self.history_up.emit()
            return

        # ↓ → historique suivant
        if key == Qt.Key.Key_Down and self.toPlainText().count("\n") == 0:
            self.history_down.emit()
            return

        super().keyPressEvent(event)

        # Auto-resize de la zone de saisie
        doc_height = int(self.document().size().height()) + 14
        new_height = max(42, min(doc_height, 120))
        self.setFixedHeight(new_height)
