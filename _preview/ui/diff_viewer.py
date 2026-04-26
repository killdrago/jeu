"""
Visualiseur de diff coloré — affiche les différences entre l'original et la modification proposée.
"""

from PyQt6.QtWidgets import QTextEdit, QWidget, QVBoxLayout, QLabel
from PyQt6.QtGui import QTextCharFormat, QColor, QFont, QTextCursor
from PyQt6.QtCore import Qt

from ui.styles import *


class DiffViewer(QTextEdit):
    """Affichage coloré d'un diff unified."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet(f"""
            QTextEdit {{
                background: {C_BG};
                color: {C_WHITE};
                border: none;
                padding: 10px;
                font-family: {FONT_MONO};
                font-size: 12px;
                line-height: 1.4;
            }}
        """)

    def set_diff(self, diff_text: str):
        """Affiche un diff unified coloré."""
        self.clear()

        if not diff_text or diff_text == "Aucune différence détectée.":
            self._append("Aucune différence détectée.", C_GRAY)
            return

        for line in diff_text.splitlines():
            if line.startswith("+++"):
                self._append(line + "\n", C_GREEN, bold=True)
            elif line.startswith("---"):
                self._append(line + "\n", C_RED, bold=True)
            elif line.startswith("@@"):
                self._append(line + "\n", C_BLUE)
            elif line.startswith("+"):
                self._append(line + "\n", C_GREEN)
            elif line.startswith("-"):
                self._append(line + "\n", C_RED)
            else:
                self._append(line + "\n", C_GRAY)

    def set_code(self, code: str, filename: str = ""):
        """Affiche du code Python coloré simplement."""
        self.clear()
        if filename:
            self._append(f"── {filename} ──\n\n", C_BLUE, bold=True)

        for line in code.splitlines():
            stripped = line.strip()
            # Coloration syntaxique basique
            if stripped.startswith("#"):
                self._append(line + "\n", C_GRAY, italic=True)
            elif any(stripped.startswith(kw) for kw in (
                "def ", "class ", "async def ", "import ", "from "
            )):
                self._append(line + "\n", C_PURPLE, bold=True)
            elif any(stripped.startswith(kw) for kw in (
                "return", "if ", "else:", "elif ", "for ", "while ",
                "try:", "except", "finally:", "with "
            )):
                self._append(line + "\n", C_BLUE)
            elif '"""' in line or "'''" in line or (
                stripped.startswith('"') or stripped.startswith("'")
            ):
                self._append(line + "\n", C_YELLOW)
            else:
                self._append(line + "\n", C_WHITE)

    def _append(self, text: str, color: str = C_WHITE,
                bold: bool = False, italic: bool = False):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        if italic:
            fmt.setFontItalic(True)
        cursor.setCharFormat(fmt)
        cursor.insertText(text)
        self.setTextCursor(cursor)
