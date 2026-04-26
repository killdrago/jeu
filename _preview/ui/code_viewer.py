"""
CodeViewer — Affiche le code Python avec surbrillance des lignes modifiées.

Les lignes modifiées/ajoutées apparaissent:
  - En GRAS
  - Avec un fond vert sombre (comme un diff +)
  - Numérotées à gauche

Les lignes normales sont affichées avec coloration syntaxique basique.
"""

from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtGui import (
    QTextCharFormat, QColor, QFont, QTextCursor,
    QTextBlockFormat
)
from PyQt6.QtCore import Qt

from ui.styles import *


# Couleurs de fond pour les lignes modifiées
BG_MODIFIED  = "#0d2b0d"   # Fond vert très sombre pour lignes modifiées
BG_NORMAL    = C_BG        # Fond normal


class CodeViewer(QTextEdit):
    """
    Visualiseur de code avec:
    - Numérotation des lignes
    - Coloration syntaxique Python basique
    - Surbrillance (fond + gras) des lignes modifiées
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.setStyleSheet(f"""
            QTextEdit {{
                background: {C_BG};
                color: {C_WHITE};
                border: none;
                padding: 4px;
                font-family: {FONT_MONO};
                font-size: 12px;
                line-height: 1.5;
            }}
            QScrollBar:vertical {{
                background: {C_BG2};
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {C_GREEN_DIM};
                border-radius: 4px;
                min-height: 20px;
            }}
        """)

    def set_code_with_highlights(
        self,
        code: str,
        filename: str = "",
        modified_lines: set = None
    ):
        """
        Affiche le code avec les lignes modifiées en surbrillance.

        Args:
            code: Le code source complet
            filename: Nom du fichier (pour l'en-tête)
            modified_lines: Set de numéros de lignes (1-indexed) à surligner
        """
        self.clear()

        if modified_lines is None:
            modified_lines = set()

        lines = code.splitlines()
        total = len(lines)
        # Largeur du numéro de ligne (ex: 3 pour 999 lignes)
        ln_width = len(str(total))

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)

        for line_num, line in enumerate(lines, start=1):
            is_modified = line_num in modified_lines

            # Format de bloc (fond de ligne)
            block_fmt = QTextBlockFormat()
            if is_modified:
                block_fmt.setBackground(QColor(BG_MODIFIED))
            else:
                block_fmt.setBackground(QColor(BG_NORMAL))
            cursor.setBlockFormat(block_fmt)

            # ── Numéro de ligne ──────────────────
            num_fmt = QTextCharFormat()
            if is_modified:
                num_fmt.setForeground(QColor(C_GREEN))
                num_fmt.setFontWeight(QFont.Weight.Bold)
                num_fmt.setBackground(QColor("#0a3a0a"))
            else:
                num_fmt.setForeground(QColor("#555555"))
                num_fmt.setBackground(QColor(C_BG2))

            cursor.setCharFormat(num_fmt)
            cursor.insertText(f" {str(line_num).rjust(ln_width)} ")

            # ── Marqueur ligne modifiée ──────────
            if is_modified:
                mark_fmt = QTextCharFormat()
                mark_fmt.setForeground(QColor(C_GREEN))
                mark_fmt.setFontWeight(QFont.Weight.Bold)
                mark_fmt.setBackground(QColor(BG_MODIFIED))
                cursor.setCharFormat(mark_fmt)
                cursor.insertText("▶ ")
            else:
                space_fmt = QTextCharFormat()
                space_fmt.setForeground(QColor(C_GRAY))
                space_fmt.setBackground(QColor(BG_NORMAL))
                cursor.setCharFormat(space_fmt)
                cursor.insertText("  ")

            # ── Contenu de la ligne ──────────────
            self._insert_colored_line(cursor, line, is_modified, block_fmt)

            # Nouvelle ligne (sauf la dernière)
            if line_num < total:
                cursor.insertBlock()

        self.setTextCursor(cursor)
        self.moveCursor(QTextCursor.MoveOperation.Start)

    def _insert_colored_line(
        self,
        cursor: QTextCursor,
        line: str,
        is_modified: bool,
        block_fmt: QTextBlockFormat
    ):
        """Insère une ligne avec coloration syntaxique basique."""
        stripped = line.strip()

        # Détermination de la couleur de base
        if stripped.startswith("#"):
            color = C_GRAY
        elif any(stripped.startswith(kw) for kw in (
            "def ", "class ", "async def "
        )):
            color = C_PURPLE
        elif any(stripped.startswith(kw) for kw in (
            "import ", "from "
        )):
            color = C_BLUE
        elif any(stripped.startswith(kw) for kw in (
            "return", "yield", "raise", "pass", "break", "continue"
        )):
            color = C_ORANGE
        elif any(stripped.startswith(kw) for kw in (
            "if ", "else:", "elif ", "for ", "while ",
            "try:", "except", "finally:", "with ", "async for", "async with"
        )):
            color = C_BLUE
        elif stripped.startswith('"""') or stripped.startswith("'''"):
            color = C_YELLOW
        elif stripped.startswith('"') or stripped.startswith("'"):
            color = C_YELLOW
        elif stripped == "" or stripped == "pass":
            color = C_WHITE
        else:
            color = C_WHITE

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        fmt.setBackground(
            QColor(BG_MODIFIED) if is_modified else QColor(BG_NORMAL)
        )

        # Les lignes modifiées sont en GRAS
        if is_modified:
            fmt.setFontWeight(QFont.Weight.Bold)
        else:
            fmt.setFontWeight(QFont.Weight.Normal)

        cursor.setCharFormat(fmt)
        cursor.insertText(line)

    def clear(self):
        """Efface le contenu."""
        super().clear()
