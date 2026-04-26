"""
Panel de validation des modifications proposées par l'IA.
Workflow:
  1. L'IA répond avec du code modifié
  2. Ce panel affiche le diff et les fichiers modifiés
  3. L'utilisateur peut: Prévisualiser → Valider ou Refuser
     - Prévisualiser: lance l'app dans _preview/ 
     - Valider: applique sur l'app de base + redémarre
     - Refuser: rollback Git + supprime _preview/
"""

import os
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTabWidget, QTextEdit, QListWidget,
    QListWidgetItem, QSplitter, QFrame, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QIcon

from ui.styles import *
from ui.diff_viewer import DiffViewer
from core.code_modifier import ModificationPlan, CodeBlock, CodeModifier
from core.git_snapshot import GitSnapshot
from core.app_reloader import AppReloader


class ModificationPanel(QWidget):
    """
    Panel latéral affiché quand l'IA propose une modification.
    """

    # Signaux vers la fenêtre principale
    log_message = pyqtSignal(str, str)    # message, couleur
    modification_applied = pyqtSignal()
    modification_refused = pyqtSignal()

    def __init__(
        self,
        modifier: CodeModifier,
        snapshot: GitSnapshot,
        reloader: AppReloader,
        parent=None
    ):
        super().__init__(parent)
        self.modifier = modifier
        self.snapshot = snapshot
        self.reloader = reloader
        self._current_plan: Optional[ModificationPlan] = None
        self._snapshot_hash: Optional[str] = None
        self._setup_ui()
        self._connect_reloader()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── En-tête ──────────────────────────────
        header = QLabel("  ◈ MODIFICATIONS PROPOSÉES PAR L'IA")
        header.setStyleSheet(HEADER_STYLE + f"QLabel {{ color: {C_YELLOW}; border-color: {C_YELLOW}; }}")
        layout.addWidget(header)

        # ── Zone de statut ────────────────────────
        self.status_frame = QFrame()
        self.status_frame.setStyleSheet(f"background: {C_BG2}; border-bottom: 1px solid {C_GRAY};")
        status_layout = QHBoxLayout(self.status_frame)
        status_layout.setContentsMargins(10, 6, 10, 6)

        self.status_icon = QLabel("○")
        self.status_icon.setStyleSheet(f"color: {C_GRAY}; font-size: 16px;")
        status_layout.addWidget(self.status_icon)

        self.status_text = QLabel("En attente d'une proposition IA…")
        self.status_text.setStyleSheet(f"color: {C_GRAY}; font-size: 12px;")
        status_layout.addWidget(self.status_text, stretch=1)

        self.file_count = QLabel("")
        self.file_count.setStyleSheet(f"color: {C_BLUE}; font-size: 11px; font-weight: bold;")
        status_layout.addWidget(self.file_count)

        layout.addWidget(self.status_frame)

        # ── Contenu principal (tabs) ──────────────
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(TAB_STYLE)

        # Tab: Fichiers modifiés
        self.files_tab = self._build_files_tab()
        self.tabs.addTab(self.files_tab, "📄 Fichiers")

        # Tab: Diff
        self.diff_tab = DiffViewer()
        self.tabs.addTab(self.diff_tab, "Δ Diff")

        # Tab: Code complet
        self.code_tab = DiffViewer()
        self.tabs.addTab(self.code_tab, "{ } Code")

        # Tab: Log preview
        self.log_tab = self._build_log_tab()
        self.tabs.addTab(self.log_tab, "📋 Log")

        layout.addWidget(self.tabs, stretch=1)

        # ── Boutons d'action ──────────────────────
        action_frame = QFrame()
        action_frame.setStyleSheet(f"background: {C_BG2}; border-top: 1px solid {C_GRAY};")
        action_layout = QVBoxLayout(action_frame)
        action_layout.setContentsMargins(10, 10, 10, 10)
        action_layout.setSpacing(8)

        # Ligne 1: Prévisualiser
        row1 = QHBoxLayout()

        self.btn_preview = QPushButton("▶  LANCER PREVIEW")
        self.btn_preview.setStyleSheet(BUTTON_WARN)
        self.btn_preview.setToolTip(
            "Lance l'app modifiée dans une fenêtre séparée pour tester"
        )
        self.btn_preview.setEnabled(False)
        self.btn_preview.clicked.connect(self._launch_preview)
        row1.addWidget(self.btn_preview)

        self.btn_stop_preview = QPushButton("■ STOP")
        self.btn_stop_preview.setStyleSheet(BUTTON_STYLE)
        self.btn_stop_preview.setEnabled(False)
        self.btn_stop_preview.clicked.connect(self._stop_preview)
        row1.addWidget(self.btn_stop_preview)

        action_layout.addLayout(row1)

        # Ligne 2: Valider / Refuser
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        self.btn_validate = QPushButton("✔  VALIDER & APPLIQUER")
        self.btn_validate.setStyleSheet(BUTTON_PRIMARY)
        self.btn_validate.setToolTip(
            "Applique les modifications sur l'app de base et la relance"
        )
        self.btn_validate.setEnabled(False)
        self.btn_validate.clicked.connect(self._validate)
        row2.addWidget(self.btn_validate)

        self.btn_refuse = QPushButton("✘  REFUSER")
        self.btn_refuse.setStyleSheet(BUTTON_DANGER)
        self.btn_refuse.setToolTip(
            "Rejette les modifications et rollback au snapshot Git"
        )
        self.btn_refuse.setEnabled(False)
        self.btn_refuse.clicked.connect(self._refuse)
        row2.addWidget(self.btn_refuse)

        action_layout.addLayout(row2)

        # Barre de progression
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background: {C_BG};
                border: 1px solid {C_GRAY};
                border-radius: 3px;
                height: 6px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background: {C_GREEN};
                border-radius: 3px;
            }}
        """)
        action_layout.addWidget(self.progress)

        layout.addWidget(action_frame)

    def _build_files_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.files_list = QListWidget()
        self.files_list.setStyleSheet(f"""
            QListWidget {{
                background: {C_BG};
                color: {C_WHITE};
                border: none;
                font-family: {FONT_MONO};
                font-size: 12px;
            }}
            QListWidget::item {{
                padding: 6px 10px;
                border-bottom: 1px solid {C_BG2};
            }}
            QListWidget::item:selected {{
                background: {C_GRAY2};
                color: {C_GREEN};
            }}
            QListWidget::item:hover {{
                background: {C_BG3};
            }}
        """)
        self.files_list.currentRowChanged.connect(self._on_file_selected)
        layout.addWidget(self.files_list)
        return widget

    def _build_log_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet(f"""
            QTextEdit {{
                background: {C_BG};
                color: {C_GREEN};
                border: none;
                padding: 8px;
                font-family: {FONT_MONO};
                font-size: 11px;
            }}
        """)
        layout.addWidget(self.log_view)
        return widget

    def _connect_reloader(self):
        """Connecte les signaux du reloader."""
        self.reloader.preview_launched.connect(
            lambda pid: self._log(f"✅ Preview lancé (PID {pid})", C_GREEN)
        )
        self.reloader.preview_stopped.connect(
            lambda: self._log("🔴 Preview arrêté", C_ORANGE)
        )
        self.reloader.preview_output.connect(
            lambda msg: self._log(msg, C_GRAY)
        )
        self.reloader.preview_crashed.connect(
            lambda err: self._log(f"❌ Crash preview: {err}", C_RED)
        )
        self.reloader.status_changed.connect(
            lambda msg: self._log(f"⚙ {msg}", C_YELLOW)
        )

    # ─────────────────────────────────────────────
    # API publique
    # ─────────────────────────────────────────────

    def load_plan(self, plan: ModificationPlan):
        """Charge un plan de modification dans le panel."""
        self._current_plan = plan
        self.files_list.clear()
        self.log_view.clear()

        if not plan.is_valid:
            self._set_status("❌ Plan invalide", C_RED)
            for err in plan.validation_errors:
                self._log(f"Erreur: {err}", C_RED)
            self._set_buttons_enabled(False)
            return

        # Crée un snapshot Git avant de toucher quoi que ce soit
        if self.snapshot.available:
            self._snapshot_hash = self.snapshot.create_snapshot(
                f"Avant modification IA — {len(plan.blocks)} fichier(s)"
            )
            self._log(
                f"📸 Snapshot Git créé: {self._snapshot_hash[:8] if self._snapshot_hash else 'N/A'}",
                C_GREEN
            )

        # Affiche les fichiers
        for i, block in enumerate(plan.blocks):
            item = QListWidgetItem(f"  {self._action_icon(block.action)} {block.filename}")
            item.setForeground(QColor(C_WHITE))
            self.files_list.addItem(item)

        self.file_count.setText(f"{len(plan.blocks)} fichier(s)")
        self._set_status("✅ Plan validé — prêt", C_GREEN)

        # Génère le diff
        diff = self.modifier.generate_diff(plan)
        self.diff_tab.set_diff(diff)

        # Affiche le code du premier fichier
        if plan.blocks:
            self.code_tab.set_code(plan.blocks[0].content, plan.blocks[0].filename)
            self.files_list.setCurrentRow(0)

        # Prépare le preview (copie dans _preview/)
        ok, msg = self.modifier.prepare_preview(plan)
        self._log(f"🗂 {msg}", C_GREEN if ok else C_RED)

        self._set_buttons_enabled(True)
        self.tabs.setCurrentIndex(1)  # Ouvre le diff

    def _action_icon(self, action: str) -> str:
        return {"replace": "✎", "create": "+", "patch": "△"}.get(action, "?")

    # ─────────────────────────────────────────────
    # Actions
    # ─────────────────────────────────────────────

    def _launch_preview(self):
        """Lance l'app preview."""
        self._log("▶ Lancement du preview…", C_YELLOW)
        self.reloader.launch_preview()
        self.btn_stop_preview.setEnabled(True)
        self.tabs.setCurrentIndex(3)  # Log

    def _stop_preview(self):
        """Arrête le preview."""
        self.reloader.stop_preview()
        self.btn_stop_preview.setEnabled(False)

    def _validate(self):
        """Valide et applique les modifications sur l'app de base."""
        if not self._current_plan:
            return

        self._log("▶ Application des modifications…", C_YELLOW)
        self._show_progress(True)

        # Stoppe le preview si lancé
        self.reloader.stop_preview()

        # Applique les modifications
        ok, msg = self.modifier.apply_plan(self._current_plan)
        self._log(msg, C_GREEN if ok else C_RED)
        self._show_progress(False)

        if ok:
            self._set_status("✅ Appliqué — relancement…", C_GREEN)
            self._set_buttons_enabled(False)

            # Snapshot post-modification
            if self.snapshot.available:
                hash_ = self.snapshot.create_snapshot(
                    "Après validation IA"
                )
                self._log(f"📸 Snapshot post-validation: {hash_[:8] if hash_ else 'N/A'}", C_GREEN)

            self.modification_applied.emit()
            self._log("🔄 Relancement de l'app de base…", C_YELLOW)
            self.reloader.restart_base_app()

        else:
            self._set_status("❌ Erreur d'application", C_RED)

    def _refuse(self):
        """Refuse et rollback."""
        self.reloader.stop_preview()

        if self._snapshot_hash and self.snapshot.available:
            ok, msg = self.snapshot.rollback_to(self._snapshot_hash)
            self._log(
                f"↩ Rollback vers {self._snapshot_hash[:8]}: {'OK' if ok else msg}",
                C_GREEN if ok else C_RED
            )

        # Nettoie le preview
        import shutil, os
        preview_dir = os.path.join(self.modifier.base_dir, "_preview")
        if os.path.exists(preview_dir):
            try:
                shutil.rmtree(preview_dir)
                self._log("🗑 Dossier _preview/ supprimé", C_GRAY)
            except Exception as e:
                self._log(f"Erreur nettoyage: {e}", C_RED)

        self._set_status("✘ Refusé — rollback effectué", C_RED)
        self._set_buttons_enabled(False)
        self._current_plan = None
        self.modification_refused.emit()

    # ─────────────────────────────────────────────
    # Sélection fichier
    # ─────────────────────────────────────────────

    def _on_file_selected(self, row: int):
        if not self._current_plan or row < 0:
            return
        if row < len(self._current_plan.blocks):
            block = self._current_plan.blocks[row]
            self.code_tab.set_code(block.content, block.filename)

    # ─────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────

    def _set_status(self, text: str, color: str):
        self.status_text.setText(text)
        self.status_text.setStyleSheet(f"color: {color}; font-size: 12px;")
        self.status_icon.setStyleSheet(f"color: {color}; font-size: 16px;")
        self.log_message.emit(text, color)

    def _log(self, msg: str, color: str = C_WHITE):
        from PyQt6.QtGui import QTextCharFormat, QColor, QFont, QTextCursor
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(msg + "\n")
        self.log_view.setTextCursor(cursor)
        self.log_view.ensureCursorVisible()

    def _set_buttons_enabled(self, enabled: bool):
        self.btn_preview.setEnabled(enabled)
        self.btn_validate.setEnabled(enabled)
        self.btn_refuse.setEnabled(enabled)

    def _show_progress(self, show: bool):
        self.progress.setVisible(show)
        if show:
            self.progress.setRange(0, 0)  # Indéterminé
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(100)
