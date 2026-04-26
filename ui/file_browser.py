"""
Navigateur de fichiers de l'app — permet de voir et éditer les fichiers sources.
"""

import os
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget,
    QTreeWidgetItem, QPushButton, QLabel, QSplitter,
    QTextEdit, QFrame, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QTextCursor, QTextCharFormat

from ui.styles import *
from ui.diff_viewer import DiffViewer


class FileBrowser(QWidget):
    """
    Onglet de navigation dans les fichiers de l'app.
    Permet de voir le contenu des fichiers pour donner du contexte à l'IA.
    """

    # Signal émis quand l'utilisateur veut demander à l'IA de modifier un fichier
    ask_ai_to_modify = pyqtSignal(str, str)  # filename, content

    def __init__(self, base_dir: str, parent=None):
        super().__init__(parent)
        self.base_dir = base_dir
        self._current_file: Optional[str] = None
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # En-tête
        header = QLabel("  ◈ FICHIERS DE L'APPLICATION")
        header.setStyleSheet(HEADER_STYLE)
        layout.addWidget(header)

        # Barre de recherche + boutons
        toolbar = QFrame()
        toolbar.setStyleSheet(f"background: {C_BG2}; border-bottom: 1px solid {C_GRAY};")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(8, 6, 8, 6)
        tb_layout.setSpacing(6)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filtrer les fichiers…")
        self.search_box.setStyleSheet(INPUT_STYLE + "QLineEdit { height: 28px; }")
        self.search_box.textChanged.connect(self._filter_tree)
        tb_layout.addWidget(self.search_box)

        refresh_btn = QPushButton("↺")
        refresh_btn.setStyleSheet(BUTTON_STYLE + "QPushButton { padding: 3px 8px; }")
        refresh_btn.clicked.connect(self.refresh)
        tb_layout.addWidget(refresh_btn)

        layout.addWidget(toolbar)

        # Splitter arbre / contenu
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background: #333; }")

        # Arbre des fichiers
        tree_panel = QWidget()
        tree_layout = QVBoxLayout(tree_panel)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.setSpacing(0)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet(f"""
            QTreeWidget {{
                background: {C_BG};
                color: {C_WHITE};
                border: none;
                border-right: 1px solid {C_GRAY};
                font-family: {FONT_MONO};
                font-size: 12px;
            }}
            QTreeWidget::item {{
                padding: 3px 5px;
            }}
            QTreeWidget::item:selected {{
                background: {C_GRAY2};
                color: {C_GREEN};
            }}
            QTreeWidget::item:hover {{
                background: {C_BG3};
            }}
        """)
        self.tree.currentItemChanged.connect(self._on_item_selected)
        tree_layout.addWidget(self.tree)

        splitter.addWidget(tree_panel)

        # Panneau de droite: contenu du fichier + actions
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Nom du fichier sélectionné
        self.file_label = QLabel("  Sélectionne un fichier…")
        self.file_label.setStyleSheet(f"""
            background: {C_BG3};
            color: {C_BLUE};
            font-family: {FONT_MONO};
            font-size: 11px;
            padding: 4px 10px;
            border-bottom: 1px solid {C_GRAY};
        """)
        right_layout.addWidget(self.file_label)

        # Visualiseur de code
        self.code_viewer = DiffViewer()
        right_layout.addWidget(self.code_viewer, stretch=1)

        # Bouton "Demander à l'IA de modifier ce fichier"
        action_bar = QFrame()
        action_bar.setStyleSheet(f"background: {C_BG2}; border-top: 1px solid {C_GRAY};")
        action_bar_layout = QHBoxLayout(action_bar)
        action_bar_layout.setContentsMargins(8, 6, 8, 6)

        self.btn_ask_ai = QPushButton("🤖  Demander à l'IA de modifier ce fichier")
        self.btn_ask_ai.setStyleSheet(BUTTON_WARN)
        self.btn_ask_ai.setEnabled(False)
        self.btn_ask_ai.clicked.connect(self._on_ask_ai)
        action_bar_layout.addWidget(self.btn_ask_ai)

        action_bar_layout.addStretch()

        self.info_label = QLabel("")
        self.info_label.setStyleSheet(f"color: {C_GRAY}; font-size: 11px;")
        action_bar_layout.addWidget(self.info_label)

        right_layout.addWidget(action_bar)
        splitter.addWidget(right_panel)

        splitter.setSizes([200, 500])
        layout.addWidget(splitter, stretch=1)

    def refresh(self):
        """Rafraîchit l'arbre des fichiers."""
        self.tree.clear()
        self._build_tree(self.base_dir, self.tree.invisibleRootItem(), "")

    def _build_tree(self, directory: str, parent_item, rel_path: str):
        """Construit récursivement l'arbre de fichiers."""
        try:
            entries = sorted(os.listdir(directory))
        except PermissionError:
            return

        # Dossiers exclus
        excluded_dirs = {"__pycache__", ".git", "_preview", "model"}

        # Dossiers d'abord
        for name in entries:
            full = os.path.join(directory, name)
            if os.path.isdir(full) and name not in excluded_dirs:
                item = QTreeWidgetItem(parent_item, [f"📁 {name}"])
                item.setForeground(0, QColor(C_BLUE))
                item.setData(0, Qt.ItemDataRole.UserRole, None)
                child_rel = f"{rel_path}/{name}".lstrip("/")
                self._build_tree(full, item, child_rel)
                item.setExpanded(True)

        # Fichiers ensuite
        ext_colors = {
            ".py": C_GREEN,
            ".json": C_YELLOW,
            ".txt": C_WHITE,
            ".bat": C_ORANGE,
            ".md": C_PURPLE,
        }
        for name in entries:
            full = os.path.join(directory, name)
            if os.path.isfile(full):
                ext = os.path.splitext(name)[1].lower()
                color = ext_colors.get(ext, C_GRAY)
                icons = {".py": "🐍", ".json": "{}", ".txt": "📄",
                         ".bat": "⚡", ".md": "📝"}
                icon = icons.get(ext, "•")
                item = QTreeWidgetItem(parent_item, [f"{icon} {name}"])
                item.setForeground(0, QColor(color))
                rel = f"{rel_path}/{name}".lstrip("/")
                item.setData(0, Qt.ItemDataRole.UserRole, rel)

    def _filter_tree(self, text: str):
        """Filtre l'arbre selon le texte de recherche."""
        def show_matching(item: QTreeWidgetItem) -> bool:
            path = item.data(0, Qt.ItemDataRole.UserRole)
            match = not text or (path and text.lower() in path.lower())

            child_match = False
            for i in range(item.childCount()):
                if show_matching(item.child(i)):
                    child_match = True

            visible = match or child_match
            item.setHidden(not visible)
            return visible

        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            show_matching(root.child(i))

    def _on_item_selected(self, item: QTreeWidgetItem, _):
        if item is None:
            return
        rel_path = item.data(0, Qt.ItemDataRole.UserRole)
        if rel_path is None:
            return  # C'est un dossier

        self._current_file = rel_path
        full_path = os.path.join(self.base_dir, rel_path)

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            size = os.path.getsize(full_path)
            lines = content.count("\n") + 1
            self.file_label.setText(f"  {rel_path}  ({lines} lignes, {size} octets)")
            self.code_viewer.set_code(content, rel_path)
            self.info_label.setText(f"{lines} lignes")
            self.btn_ask_ai.setEnabled(True)
        except Exception as e:
            self.file_label.setText(f"  {rel_path}  ⚠️ Erreur: {e}")
            self.code_viewer.clear()
            self.btn_ask_ai.setEnabled(False)

    def _on_ask_ai(self):
        """Demande à l'IA de modifier le fichier sélectionné."""
        if not self._current_file:
            return
        full_path = os.path.join(self.base_dir, self._current_file)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.ask_ai_to_modify.emit(self._current_file, content)
        except Exception as e:
            pass
