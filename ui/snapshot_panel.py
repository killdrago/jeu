"""
Panel d'historique Git — liste des snapshots et rollback.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QFrame
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor

from ui.styles import *
from core.git_snapshot import GitSnapshot


class SnapshotPanel(QWidget):
    """Panel d'affichage et gestion des snapshots Git."""

    rollback_done = pyqtSignal(str)  # message

    def __init__(self, snapshot: GitSnapshot, parent=None):
        super().__init__(parent)
        self.snapshot = snapshot
        self._history = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # En-tête
        header = QLabel("  ◈ HISTORIQUE DES SNAPSHOTS")
        header.setStyleSheet(HEADER_STYLE)
        layout.addWidget(header)

        # Toolbar
        toolbar = QFrame()
        toolbar.setStyleSheet(f"background: {C_BG2}; border-bottom: 1px solid {C_GRAY};")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(8, 6, 8, 6)

        self.btn_snapshot = QPushButton("📸  CRÉER SNAPSHOT")
        self.btn_snapshot.setStyleSheet(BUTTON_PRIMARY)
        self.btn_snapshot.clicked.connect(self._create_snapshot)
        tb.addWidget(self.btn_snapshot)

        self.btn_refresh = QPushButton("↺  RAFRAÎCHIR")
        self.btn_refresh.setStyleSheet(BUTTON_STYLE)
        self.btn_refresh.clicked.connect(self.refresh)
        tb.addWidget(self.btn_refresh)

        tb.addStretch()

        self.git_status = QLabel()
        if self.snapshot.available:
            self.git_status.setText("● Git actif")
            self.git_status.setStyleSheet(f"color: {C_GREEN}; font-size: 11px;")
        else:
            self.git_status.setText("○ Git non disponible")
            self.git_status.setStyleSheet(f"color: {C_RED}; font-size: 11px;")
        tb.addWidget(self.git_status)

        layout.addWidget(toolbar)

        # Liste des snapshots
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background: {C_BG};
                color: {C_WHITE};
                border: none;
                font-family: {FONT_MONO};
                font-size: 12px;
            }}
            QListWidget::item {{
                padding: 8px 12px;
                border-bottom: 1px solid {C_BG2};
            }}
            QListWidget::item:selected {{
                background: {C_GRAY2};
                color: {C_GREEN};
            }}
        """)
        layout.addWidget(self.list_widget, stretch=1)

        # Action rollback
        action_bar = QFrame()
        action_bar.setStyleSheet(f"background: {C_BG2}; border-top: 1px solid {C_GRAY};")
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(8, 8, 8, 8)

        self.btn_rollback = QPushButton("↩  ROLLBACK AU SNAPSHOT SÉLECTIONNÉ")
        self.btn_rollback.setStyleSheet(BUTTON_DANGER)
        self.btn_rollback.setEnabled(False)
        self.btn_rollback.clicked.connect(self._rollback)
        action_layout.addWidget(self.btn_rollback)

        action_layout.addStretch()

        self.selected_info = QLabel("Sélectionne un snapshot pour rollback")
        self.selected_info.setStyleSheet(f"color: {C_GRAY}; font-size: 11px;")
        action_layout.addWidget(self.selected_info)

        layout.addWidget(action_bar)

        self.list_widget.currentRowChanged.connect(self._on_selection_changed)

        if self.snapshot.available:
            self.refresh()

    def refresh(self):
        """Recharge l'historique des snapshots."""
        self.list_widget.clear()
        self._history = self.snapshot.get_history(20)

        if not self._history:
            item = QListWidgetItem("  Aucun snapshot disponible")
            item.setForeground(QColor(C_GRAY))
            self.list_widget.addItem(item)
            return

        for entry in self._history:
            text = (
                f"  [{entry['hash']}]  {entry['message']}\n"
                f"  {entry['date']}"
            )
            item = QListWidgetItem(text)
            if "[SNAPSHOT]" in entry["message"]:
                item.setForeground(QColor(C_GREEN))
            elif "Initial" in entry["message"]:
                item.setForeground(QColor(C_BLUE))
            else:
                item.setForeground(QColor(C_WHITE))
            item.setData(Qt.ItemDataRole.UserRole, entry["full_hash"])
            self.list_widget.addItem(item)

    def _create_snapshot(self):
        """Crée un snapshot manuel."""
        if not self.snapshot.available:
            return
        hash_ = self.snapshot.create_snapshot("Manuel via Admin Console")
        if hash_:
            self.rollback_done.emit(
                f"📸 Snapshot créé: {hash_[:8]}"
            )
            self.refresh()

    def _on_selection_changed(self, row: int):
        if row < 0 or row >= len(self._history):
            self.btn_rollback.setEnabled(False)
            self.selected_info.setText("Sélectionne un snapshot pour rollback")
            return
        entry = self._history[row]
        self.btn_rollback.setEnabled(True)
        self.selected_info.setText(f"→ {entry['hash']} : {entry['message'][:40]}")

    def _rollback(self):
        """Effectue le rollback vers le snapshot sélectionné."""
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self._history):
            return

        entry = self._history[row]
        ok, msg = self.snapshot.rollback_to(entry["full_hash"])
        if ok:
            self.rollback_done.emit(f"✅ Rollback vers {entry['hash']}")
            self.refresh()
        else:
            self.rollback_done.emit(f"❌ Rollback échoué: {msg[:60]}")
