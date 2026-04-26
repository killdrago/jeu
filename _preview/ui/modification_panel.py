"""
Panel de validation des modifications proposées par l'IA.
Workflow:
  1. L'IA répond avec du code modifié (format ## FILE:)
  2. Ce panel affiche AUTOMATIQUEMENT le diff coloré à droite
  3. L'utilisateur voit immédiatement les changements proposés
  4. Il peut: Prévisualiser → Valider ou Refuser
     - Prévisualiser: lance l'app dans _preview/
     - Valider:  applique sur l'app de base + redémarre
     - Refuser:  rollback Git + supprime _preview/
"""

import os
import shutil
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTabWidget, QTextEdit, QListWidget,
    QListWidgetItem, QSplitter, QFrame, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor

from ui.styles import *
from ui.diff_viewer import DiffViewer
from core.code_modifier import ModificationPlan, CodeBlock, CodeModifier
from core.git_snapshot import GitSnapshot
from core.app_reloader import AppReloader


class ModificationPanel(QWidget):
    """
    Panel latéral affiché quand l'IA propose une modification.
    Le diff apparaît automatiquement à droite dès que l'IA répond.
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

    # ─────────────────────────────────────────────
    # Construction de l'UI
    # ─────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── En-tête ──────────────────────────────
        self.header = QLabel("  ◈ MODIFICATIONS PROPOSÉES PAR L'IA")
        self.header.setStyleSheet(
            HEADER_STYLE + f"QLabel {{ color: {C_GRAY}; border-color: {C_GRAY}; }}"
        )
        layout.addWidget(self.header)

        # ── Zone de statut ────────────────────────
        self.status_frame = QFrame()
        self.status_frame.setStyleSheet(
            f"background: {C_BG2}; border-bottom: 1px solid {C_GRAY};"
        )
        status_layout = QHBoxLayout(self.status_frame)
        status_layout.setContentsMargins(10, 6, 10, 6)

        self.status_icon = QLabel("○")
        self.status_icon.setStyleSheet(f"color: {C_GRAY}; font-size: 16px;")
        status_layout.addWidget(self.status_icon)

        self.status_text = QLabel("En attente d'une proposition IA…")
        self.status_text.setStyleSheet(
            f"color: {C_GRAY}; font-size: 12px;"
        )
        status_layout.addWidget(self.status_text, stretch=1)

        self.file_count = QLabel("")
        self.file_count.setStyleSheet(
            f"color: {C_BLUE}; font-size: 11px; font-weight: bold;"
        )
        status_layout.addWidget(self.file_count)

        layout.addWidget(self.status_frame)

        # ── Contenu principal (tabs) ──────────────
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(TAB_STYLE)

        # Tab: Diff coloré (affiché en premier)
        self.diff_tab = DiffViewer()
        self.tabs.addTab(self.diff_tab, "Δ Diff")

        # Tab: Code complet proposé
        self.code_tab = DiffViewer()
        self.tabs.addTab(self.code_tab, "{ } Code")

        # Tab: Fichiers modifiés
        self.files_tab = self._build_files_tab()
        self.tabs.addTab(self.files_tab, "📄 Fichiers")

        # Tab: Log preview
        self.log_tab = self._build_log_tab()
        self.tabs.addTab(self.log_tab, "📋 Log")

        layout.addWidget(self.tabs, stretch=1)

        # ── Boutons d'action ──────────────────────
        action_frame = QFrame()
        action_frame.setStyleSheet(
            f"background: {C_BG2}; border-top: 1px solid {C_GRAY};"
        )
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
            lambda line: self._log(line, C_GRAY)
        )
        self.reloader.preview_crashed.connect(
            lambda err: self._log(f"❌ Crash preview: {err}", C_RED)
        )

    # ─────────────────────────────────────────────
    # API publique — appelée depuis main_window
    # ─────────────────────────────────────────────

    def load_plan(self, plan: ModificationPlan):
        """
        Charge un plan de modification et l'affiche IMMÉDIATEMENT
        dans le panneau droit (diff + fichiers + code).
        Appelé automatiquement dès que l'IA propose du code.
        """
        self._current_plan = plan
        nb = len(plan.blocks)

        # ── Met à jour le statut ─────────────────
        self._set_active_state(nb)

        # ── Remplit la liste des fichiers ────────
        self.files_list.clear()
        for block in plan.blocks:
            item = QListWidgetItem(f"  📝 {block.filename}")
            item.setForeground(QColor(C_YELLOW))
            self.files_list.addItem(item)

        # ── Génère et affiche le diff ─────────────
        diff_text = self.modifier.generate_diff(plan)
        self.diff_tab.set_diff(diff_text)

        # ── Affiche le code complet du 1er fichier ─
        if plan.blocks:
            self.code_tab.set_code(
                plan.blocks[0].content,
                plan.blocks[0].filename
            )

        # ── Bascule automatiquement sur l'onglet Diff ──
        self.tabs.setCurrentIndex(0)  # Onglet "Δ Diff"

        # ── Active les boutons ───────────────────
        self.btn_validate.setEnabled(True)
        self.btn_refuse.setEnabled(True)
        self.btn_preview.setEnabled(True)

        # ── Log ──────────────────────────────────
        self._log(
            f"📥 Plan reçu: {nb} fichier(s) à modifier\n"
            + "\n".join(f"  • {b.filename}" for b in plan.blocks),
            C_YELLOW
        )

    def _set_active_state(self, nb_files: int):
        """Met à jour l'en-tête et le statut quand un plan est chargé."""
        # En-tête en jaune = modification en attente
        self.header.setText(
            f"  ◈ MODIFICATIONS EN ATTENTE — {nb_files} FICHIER(S)"
        )
        self.header.setStyleSheet(
            HEADER_STYLE
            + f"QLabel {{ color: {C_YELLOW}; border-color: {C_YELLOW}; "
            f"background: #1a1400; }}"
        )

        self.status_icon.setText("●")
        self.status_icon.setStyleSheet(f"color: {C_YELLOW}; font-size: 16px;")

        self.status_text.setText(
            "Code modifié prêt — Valider ou Refuser ci-dessous"
        )
        self.status_text.setStyleSheet(
            f"color: {C_YELLOW}; font-size: 12px; font-weight: bold;"
        )
        self.file_count.setText(f"[{nb_files} fichier(s)]")

    def _reset_state(self):
        """Remet le panel dans l'état neutre après validation/refus."""
        self.header.setText("  ◈ MODIFICATIONS PROPOSÉES PAR L'IA")
        self.header.setStyleSheet(
            HEADER_STYLE
            + f"QLabel {{ color: {C_GRAY}; border-color: {C_GRAY}; }}"
        )
        self.status_icon.setText("○")
        self.status_icon.setStyleSheet(f"color: {C_GRAY}; font-size: 16px;")
        self.status_text.setText("En attente d'une proposition IA…")
        self.status_text.setStyleSheet(f"color: {C_GRAY}; font-size: 12px;")
        self.file_count.setText("")

        self.btn_validate.setEnabled(False)
        self.btn_refuse.setEnabled(False)
        self.btn_preview.setEnabled(False)
        self.btn_stop_preview.setEnabled(False)

        self._current_plan = None

    # ─────────────────────────────────────────────
    # Slots liste de fichiers
    # ─────────────────────────────────────────────

    def _on_file_selected(self, row: int):
        """Affiche le code du fichier sélectionné dans l'onglet Code."""
        if not self._current_plan or row < 0:
            return
        if row >= len(self._current_plan.blocks):
            return
        block = self._current_plan.blocks[row]
        self.code_tab.set_code(block.content, block.filename)

    # ─────────────────────────────────────────────
    # Actions boutons
    # ─────────────────────────────────────────────

    def _launch_preview(self):
        """Prépare et lance l'app preview dans un process séparé."""
        if not self._current_plan:
            return

        self._log("🔧 Préparation du preview…", C_YELLOW)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # indéterminé

        ok, msg = self.modifier.prepare_preview(self._current_plan)

        self.progress.setVisible(False)

        if not ok:
            self._log(f"❌ {msg}", C_RED)
            self.log_message.emit(f"❌ Preview échoué: {msg}", C_RED)
            return

        self._log(f"✅ {msg}", C_GREEN)
        self.reloader.launch_preview()
        self.btn_stop_preview.setEnabled(True)
        self.tabs.setCurrentIndex(3)  # Bascule sur le log

    def _stop_preview(self):
        """Arrête l'app preview."""
        self.reloader.stop_preview()
        self.btn_stop_preview.setEnabled(False)

    def _validate(self):
        """
        Valide et applique les modifications sur l'app de base.
        1. Crée un snapshot Git avant
        2. Applique les fichiers
        3. Crée un snapshot Git après
        4. Relance l'app
        """
        if not self._current_plan:
            return

        # Désactive les boutons pendant l'opération
        self.btn_validate.setEnabled(False)
        self.btn_refuse.setEnabled(False)
        self.btn_preview.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)

        self._log("💾 Création snapshot Git avant modification…", C_YELLOW)

        # Snapshot avant
        if self.snapshot.available:
            hash_before = self.snapshot.create_snapshot(
                f"Avant modif IA: {', '.join(b.filename for b in self._current_plan.blocks)}"
            )
            if hash_before:
                self._log(f"📸 Snapshot: {hash_before[:8]}", C_GREEN)

        # Applique les modifications
        self._log("✍ Application des modifications…", C_YELLOW)
        ok, msg = self.modifier.apply_plan(self._current_plan)

        self.progress.setVisible(False)

        if not ok:
            self._log(f"❌ Erreur: {msg}", C_RED)
            self.log_message.emit(f"❌ Erreur application: {msg}", C_RED)
            self.btn_validate.setEnabled(True)
            self.btn_refuse.setEnabled(True)
            return

        self._log(f"✅ {msg}", C_GREEN)

        # Snapshot après
        if self.snapshot.available:
            hash_after = self.snapshot.create_snapshot(
                f"Après modif IA: {', '.join(b.filename for b in self._current_plan.blocks)}"
            )
            if hash_after:
                self._log(f"📸 Snapshot post-modif: {hash_after[:8]}", C_GREEN)

        # Nettoie le preview si existant
        self._cleanup_preview()

        self.log_message.emit("✅ Modifications appliquées !", C_GREEN)
        self.modification_applied.emit()

        # Statut succès sur le panneau
        self.header.setText("  ✅ MODIFICATIONS APPLIQUÉES")
        self.header.setStyleSheet(
            HEADER_STYLE
            + f"QLabel {{ color: {C_GREEN}; border-color: {C_GREEN}; "
            f"background: #001a00; }}"
        )
        self.status_text.setText("Modifications appliquées avec succès !")
        self.status_text.setStyleSheet(f"color: {C_GREEN}; font-size: 12px; font-weight: bold;")
        self.status_icon.setText("✔")
        self.status_icon.setStyleSheet(f"color: {C_GREEN}; font-size: 16px;")
        self.file_count.setText("")

        # Remet à zéro après 3 secondes
        QTimer.singleShot(3000, self._reset_state)

    def _refuse(self):
        """
        Refuse les modifications.
        → Rollback Git automatique
        → Supprime le dossier _preview/ s'il existe
        """
        if not self._current_plan:
            return

        self._log("✘ Refus des modifications…", C_RED)

        # Arrête le preview si en cours
        if self.reloader.is_preview_running():
            self.reloader.stop_preview()

        # Nettoie le preview
        self._cleanup_preview()

        # Rollback Git si on avait un snapshot
        if self.snapshot.available and self._snapshot_hash:
            ok = self.snapshot.rollback(self._snapshot_hash)
            if ok:
                self._log(
                    f"↩ Rollback effectué vers {self._snapshot_hash[:8]}",
                    C_ORANGE
                )
            else:
                self._log("⚠️ Rollback Git échoué (fichiers non modifiés)", C_ORANGE)
        else:
            self._log("ℹ Aucun snapshot — fichiers non modifiés", C_GRAY)

        self.log_message.emit("✘ Modifications refusées", C_RED)
        self.modification_refused.emit()

        # Statut refus sur le panneau
        self.header.setText("  ✘ MODIFICATIONS REFUSÉES")
        self.header.setStyleSheet(
            HEADER_STYLE
            + f"QLabel {{ color: {C_RED}; border-color: {C_RED}; "
            f"background: #1a0000; }}"
        )
        self.status_text.setText("Modifications abandonnées.")
        self.status_text.setStyleSheet(f"color: {C_RED}; font-size: 12px;")
        self.status_icon.setText("✘")
        self.status_icon.setStyleSheet(f"color: {C_RED}; font-size: 16px;")
        self.file_count.setText("")

        self.btn_validate.setEnabled(False)
        self.btn_refuse.setEnabled(False)
        self.btn_preview.setEnabled(False)
        self.btn_stop_preview.setEnabled(False)

        # Remet à zéro après 2 secondes
        QTimer.singleShot(2000, self._reset_state)

    # ─────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────

    def _cleanup_preview(self):
        """Supprime le dossier _preview/ s'il existe."""
        preview_dir = self.modifier.preview_dir
        if os.path.exists(preview_dir):
            try:
                shutil.rmtree(preview_dir)
                self._log("🗑 Dossier _preview/ supprimé", C_GRAY)
            except Exception as e:
                self._log(f"⚠️ Impossible de supprimer _preview/: {e}", C_ORANGE)

    def _log(self, message: str, color: str = C_GREEN):
        """Ajoute un message dans le log."""
        from PyQt6.QtGui import QTextCursor, QTextCharFormat, QFont, QColor as QC
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QC(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(f"{message}\n")
        self.log_view.setTextCursor(cursor)
        self.log_view.ensureCursorVisible()
        # Émet aussi vers la statusbar
        self.log_message.emit(message.split("\n")[0][:80], color)
