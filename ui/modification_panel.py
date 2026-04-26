"""
Panel de validation des modifications proposées par l'IA.

NOUVEAU WORKFLOW:
  1. L'IA répond avec du code modifié (format ## FILE:)
  2. Le panneau droit s'active automatiquement avec:
     - Onglet "Δ Diff" : diff coloré
     - Onglet "{ } Code" : code avec lignes modifiées surlignées
     - Onglet "📄 Fichiers" : liste des fichiers avec vue code inline
     - Onglet "🖥 Preview" : l'app modifiée lancée en sous-processus
                             (output log + bouton ouvrir fenêtre)
     - Onglet "📋 Log" : log d'opérations
  3. Boutons: [✔ VALIDER & APPLIQUER] et [✘ REFUSER] EN BAS
     - Valider: applique sur l'app de base → recharge
     - Refuser: rollback Git, oublie tout
"""

import os
import shutil
import difflib
from typing import Optional, List, Tuple

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTabWidget, QTextEdit, QListWidget,
    QListWidgetItem, QSplitter, QFrame, QProgressBar,
    QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QTextCharFormat, QFont, QTextCursor

from ui.styles import *
from ui.diff_viewer import DiffViewer
from ui.code_viewer import CodeViewer
from core.code_modifier import ModificationPlan, CodeBlock, CodeModifier
from core.git_snapshot import GitSnapshot
from core.app_reloader import AppReloader


class ModificationPanel(QWidget):
    """
    Panel latéral affiché quand l'IA propose une modification.
    Le panneau s'active automatiquement dès que l'IA propose du code.
    Preview = log du sous-processus + option d'ouvrir la fenêtre.
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
        self._preview_running = False
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

        # Tab 0: Diff coloré
        self.diff_tab = DiffViewer()
        self.tabs.addTab(self.diff_tab, "Δ Diff")

        # Tab 1: Code avec surbrillance des lignes modifiées
        self.code_tab = self._build_code_tab()
        self.tabs.addTab(self.code_tab, "{ } Code")

        # Tab 2: Preview (log de l'app lancée)
        self.preview_tab = self._build_preview_tab()
        self.tabs.addTab(self.preview_tab, "🖥 Preview")

        # Tab 3: Log
        self.log_tab = self._build_log_tab()
        self.tabs.addTab(self.log_tab, "📋 Log")

        layout.addWidget(self.tabs, stretch=1)

        # ── Boutons d'action ──────────────────────
        action_frame = QFrame()
        action_frame.setStyleSheet(
            f"background: {C_BG2}; border-top: 2px solid {C_GRAY};"
        )
        action_layout = QVBoxLayout(action_frame)
        action_layout.setContentsMargins(10, 10, 10, 10)
        action_layout.setSpacing(8)

        # Ligne 1: Lancer le preview
        row1 = QHBoxLayout()

        self.btn_preview = QPushButton("▶  TESTER (Preview)")
        self.btn_preview.setStyleSheet(BUTTON_WARN)
        self.btn_preview.setToolTip(
            "Lance l'app modifiée dans un sous-processus et affiche son output ici"
        )
        self.btn_preview.setEnabled(False)
        self.btn_preview.clicked.connect(self._launch_preview)
        row1.addWidget(self.btn_preview)

        self.btn_stop_preview = QPushButton("■ STOP PREVIEW")
        self.btn_stop_preview.setStyleSheet(BUTTON_STYLE)
        self.btn_stop_preview.setEnabled(False)
        self.btn_stop_preview.clicked.connect(self._stop_preview)
        row1.addWidget(self.btn_stop_preview)

        action_layout.addLayout(row1)

        # Ligne 2: Valider / Refuser
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        self.btn_validate = QPushButton("✔  ACCEPTER & APPLIQUER")
        self.btn_validate.setStyleSheet(BUTTON_PRIMARY)
        self.btn_validate.setToolTip(
            "Applique les modifications sur l'app de base et recharge"
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

    def _build_code_tab(self) -> QWidget:
        """
        Onglet Code: splitter vertical.
        - En haut: liste des fichiers modifiés (cliquables)
        - En bas: code du fichier avec lignes modifiées surlignées
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setStyleSheet("QSplitter::handle { background: #333; height: 3px; }")

        # Liste des fichiers modifiés
        files_frame = QWidget()
        files_layout = QVBoxLayout(files_frame)
        files_layout.setContentsMargins(0, 0, 0, 0)
        files_layout.setSpacing(0)

        files_header = QLabel("  📄 FICHIERS MODIFIÉS — clique pour voir le code")
        files_header.setStyleSheet(f"""
            background: {C_BG3};
            color: {C_YELLOW};
            font-family: {FONT_MONO};
            font-size: 11px;
            font-weight: bold;
            padding: 5px 8px;
            border-bottom: 1px solid {C_GRAY};
        """)
        files_layout.addWidget(files_header)

        self.code_files_list = QListWidget()
        self.code_files_list.setStyleSheet(f"""
            QListWidget {{
                background: {C_BG};
                color: {C_WHITE};
                border: none;
                font-family: {FONT_MONO};
                font-size: 12px;
                max-height: 120px;
            }}
            QListWidget::item {{
                padding: 6px 12px;
                border-bottom: 1px solid {C_BG2};
            }}
            QListWidget::item:selected {{
                background: {C_GRAY2};
                color: {C_GREEN};
            }}
            QListWidget::item:hover {{
                background: {C_BG3};
                color: {C_YELLOW};
            }}
        """)
        self.code_files_list.setMaximumHeight(120)
        self.code_files_list.currentRowChanged.connect(self._on_code_file_selected)
        files_layout.addWidget(self.code_files_list)
        splitter.addWidget(files_frame)

        # Zone d'affichage du code avec surbrillance
        code_frame = QWidget()
        code_layout = QVBoxLayout(code_frame)
        code_layout.setContentsMargins(0, 0, 0, 0)
        code_layout.setSpacing(0)

        self.code_file_label = QLabel("  Clique sur un fichier ci-dessus pour voir son code")
        self.code_file_label.setStyleSheet(f"""
            background: {C_BG3};
            color: {C_BLUE};
            font-family: {FONT_MONO};
            font-size: 11px;
            padding: 4px 10px;
            border-bottom: 1px solid {C_GRAY};
        """)
        code_layout.addWidget(self.code_file_label)

        # Légende
        legend = QLabel(
            "  ■ Fond vert = ligne ajoutée/modifiée   ■ Fond rouge = ligne supprimée"
        )
        legend.setStyleSheet(f"""
            background: {C_BG2};
            color: {C_GRAY};
            font-family: {FONT_MONO};
            font-size: 10px;
            padding: 3px 10px;
            border-bottom: 1px solid {C_GRAY};
        """)
        code_layout.addWidget(legend)

        # CodeViewer avec surbrillance des lignes modifiées
        self.code_viewer = CodeViewer()
        code_layout.addWidget(self.code_viewer, stretch=1)

        splitter.addWidget(code_frame)
        splitter.setSizes([120, 400])

        layout.addWidget(splitter, stretch=1)
        return widget

    def _build_preview_tab(self) -> QWidget:
        """Onglet Preview: output du sous-processus de l'app modifiée."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Barre de statut preview
        preview_bar = QFrame()
        preview_bar.setStyleSheet(f"background: {C_BG3}; border-bottom: 1px solid {C_GRAY};")
        pb_layout = QHBoxLayout(preview_bar)
        pb_layout.setContentsMargins(8, 4, 8, 4)

        self.preview_status_dot = QLabel("○")
        self.preview_status_dot.setStyleSheet(f"color: {C_GRAY}; font-size: 14px;")
        pb_layout.addWidget(self.preview_status_dot)

        self.preview_status_label = QLabel("Preview non lancé — Clique sur ▶ TESTER")
        self.preview_status_label.setStyleSheet(f"color: {C_GRAY}; font-size: 11px;")
        pb_layout.addWidget(self.preview_status_label, stretch=1)

        self.btn_open_window = QPushButton("⬡ Ouvrir en fenêtre séparée")
        self.btn_open_window.setStyleSheet(BUTTON_STYLE + "QPushButton { font-size: 11px; padding: 2px 8px; }")
        self.btn_open_window.setEnabled(False)
        self.btn_open_window.clicked.connect(self._open_preview_window)
        pb_layout.addWidget(self.btn_open_window)

        layout.addWidget(preview_bar)

        # Log de sortie de l'app preview
        self.preview_log = QTextEdit()
        self.preview_log.setReadOnly(True)
        self.preview_log.setStyleSheet(f"""
            QTextEdit {{
                background: {C_BG};
                color: {C_GREEN};
                border: none;
                padding: 8px;
                font-family: {FONT_MONO};
                font-size: 11px;
            }}
        """)
        layout.addWidget(self.preview_log, stretch=1)

        # Message informatif
        info = QLabel(
            "  ℹ  L'app modifiée se lance dans un sous-processus. Son output apparaît ici.\n"
            "  Utilise 'Ouvrir en fenêtre séparée' si l'app est une app graphique."
        )
        info.setStyleSheet(f"""
            background: {C_BG2};
            color: {C_GRAY};
            font-family: {FONT_MONO};
            font-size: 10px;
            padding: 5px 10px;
            border-top: 1px solid {C_GRAY};
        """)
        info.setWordWrap(True)
        layout.addWidget(info)

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
                font-size: 12px;
            }}
        """)
        layout.addWidget(self.log_view)
        return widget

    def _connect_reloader(self):
        """Connecte les signaux du reloader."""
        self.reloader.preview_launched.connect(self._on_preview_launched)
        self.reloader.preview_stopped.connect(self._on_preview_stopped)
        self.reloader.preview_output.connect(self._on_preview_output)
        self.reloader.preview_crashed.connect(self._on_preview_crashed)
        self.reloader.status_changed.connect(
            lambda msg: self._log(msg, C_BLUE)
        )

    # ─────────────────────────────────────────────
    # API publique
    # ─────────────────────────────────────────────

    def propose_modification(self, ai_response: str):
        """
        Point d'entrée principal: parse la réponse IA et active le panel.
        Appelé automatiquement par MainWindow quand l'IA finit de répondre.
        """
        # Stop preview en cours
        if self._preview_running:
            self._stop_preview()

        # Nettoie l'état précédent
        self._reset_state()

        # Parse la réponse
        plan = self.modifier.build_modification_plan(ai_response)

        if not plan.is_valid:
            errors = "\n".join(plan.validation_errors)
            self._set_status(f"❌ Aucune modification valide détectée", C_RED)
            self._log(f"❌ Erreurs:\n{errors}", C_RED)
            return

        self._current_plan = plan

        # Crée un snapshot Git avant toute modification
        if self.snapshot.available:
            self._log("📸 Création d'un snapshot Git de sécurité…", C_YELLOW)
            self._snapshot_hash = self.snapshot.create_snapshot(
                "Avant modification IA"
            )
            if self._snapshot_hash:
                self._log(f"✅ Snapshot: {self._snapshot_hash[:8]}", C_GREEN)

        # Prépare le preview (copie dans _preview/)
        ok, msg = self.modifier.prepare_preview(plan)
        if not ok:
            self._log(f"❌ Erreur préparation preview: {msg}", C_RED)
            return

        n = len(plan.blocks)
        self._set_status(
            f"● {n} fichier(s) modifié(s) — Teste ou Accepte/Refuse",
            C_YELLOW
        )

        # Met à jour tous les onglets
        self._populate_diff_tab(plan)
        self._populate_code_tab(plan)
        self._log(
            f"✅ Plan de modification prêt: {n} fichier(s)\n"
            + "\n".join(f"  • {b.filename}" for b in plan.blocks),
            C_GREEN
        )

        # Active les boutons
        self.btn_preview.setEnabled(True)
        self.btn_validate.setEnabled(True)
        self.btn_refuse.setEnabled(True)

        # Met à jour l'en-tête
        self.header.setStyleSheet(
            HEADER_STYLE + f"QLabel {{ color: {C_YELLOW}; border-color: {C_YELLOW}; }}"
        )
        self.file_count.setText(f"{n} fichier(s)")

        # Bascule sur l'onglet Code par défaut
        self.tabs.setCurrentIndex(1)

    def _reset_state(self):
        """Remet le panel à zéro."""
        self._current_plan = None
        self._snapshot_hash = None
        self.diff_tab.clear()
        self.code_files_list.clear()
        self.code_viewer.clear()
        self.preview_log.clear()
        self.log_view.clear()
        self.btn_preview.setEnabled(False)
        self.btn_validate.setEnabled(False)
        self.btn_refuse.setEnabled(False)
        self.btn_stop_preview.setEnabled(False)
        self.btn_open_window.setEnabled(False)
        self.file_count.setText("")
        self._set_status("En attente d'une proposition IA…", C_GRAY)
        self.header.setStyleSheet(
            HEADER_STYLE + f"QLabel {{ color: {C_GRAY}; border-color: {C_GRAY}; }}"
        )
        self._update_preview_status("○", "Preview non lancé", C_GRAY)

    # ─────────────────────────────────────────────
    # Population des onglets
    # ─────────────────────────────────────────────

    def _populate_diff_tab(self, plan: ModificationPlan):
        """Remplit l'onglet diff avec le diff coloré."""
        diff_text = self.modifier.generate_diff(plan)
        self.diff_tab.set_diff(diff_text)

    def _populate_code_tab(self, plan: ModificationPlan):
        """Remplit l'onglet Code avec la liste des fichiers modifiés."""
        self.code_files_list.clear()
        for block in plan.blocks:
            item = QListWidgetItem(f"  🐍 {block.filename}")
            item.setForeground(QColor(C_GREEN))
            item.setData(Qt.ItemDataRole.UserRole, block)
            self.code_files_list.addItem(item)

        # Sélectionne automatiquement le premier fichier
        if self.code_files_list.count() > 0:
            self.code_files_list.setCurrentRow(0)

    def _on_code_file_selected(self, row: int):
        """Quand l'utilisateur clique sur un fichier dans l'onglet Code."""
        if row < 0:
            return
        item = self.code_files_list.item(row)
        if not item:
            return
        block = item.data(Qt.ItemDataRole.UserRole)
        if not block:
            return

        self.code_file_label.setText(
            f"  📄 {block.filename}  —  lignes modifiées surlignées en vert"
        )

        # Calcule les lignes modifiées par diff
        modified_lines = self._get_modified_line_numbers(block)

        # Affiche le code avec surbrillance
        self.code_viewer.set_code_with_highlights(
            block.content,
            block.filename,
            modified_lines
        )

    def _get_modified_line_numbers(self, block: "CodeBlock") -> set:
        """Retourne les numéros de lignes (1-indexed) modifiées dans le nouveau code."""
        original_path = os.path.join(self.modifier.base_dir, block.filename)
        if not os.path.exists(original_path):
            # Fichier nouveau: toutes les lignes sont "nouvelles"
            return set(range(1, len(block.content.splitlines()) + 1))

        try:
            with open(original_path, "r", encoding="utf-8") as f:
                original_lines = f.readlines()
        except Exception:
            return set()

        new_lines = block.content.splitlines(keepends=True)

        # Utilise SequenceMatcher pour trouver les lignes modifiées
        matcher = difflib.SequenceMatcher(None, original_lines, new_lines)
        modified = set()

        for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
            if opcode in ("replace", "insert"):
                # b0..b1 sont les lignes nouvelles/modifiées (1-indexed)
                for i in range(b0 + 1, b1 + 1):
                    modified.add(i)

        return modified

    # ─────────────────────────────────────────────
    # Preview
    # ─────────────────────────────────────────────

    def _launch_preview(self):
        """Lance l'app modifiée en sous-processus."""
        if not self._current_plan:
            return

        self.preview_log.clear()
        self._log_preview("▶ Lancement du preview…\n", C_YELLOW)
        self._update_preview_status("◌", "Lancement…", C_YELLOW)

        # Bascule sur l'onglet Preview
        self.tabs.setCurrentIndex(2)

        self.btn_preview.setEnabled(False)
        self.btn_stop_preview.setEnabled(True)
        self._preview_running = True

        self.reloader.launch_preview()

    def _stop_preview(self):
        """Stoppe l'app preview."""
        self.reloader.stop_preview()
        self._preview_running = False
        self.btn_preview.setEnabled(True)
        self.btn_stop_preview.setEnabled(False)
        self.btn_open_window.setEnabled(False)
        self._update_preview_status("○", "Preview arrêté", C_GRAY)

    def _open_preview_window(self):
        """Ouvre l'app preview dans une fenêtre séparée (déjà lancée)."""
        # Le preview est déjà lancé, cette action force une nouvelle fenêtre
        self._log_preview("⬡ L'app preview est déjà en cours (voir icône dans la barre).\n", C_BLUE)

    def _on_preview_launched(self, pid: int):
        self._log_preview(f"✅ App preview lancée (PID: {pid})\n", C_GREEN)
        self._update_preview_status("●", f"Running (PID {pid})", C_GREEN)
        self.btn_open_window.setEnabled(True)
        self._log(f"🟢 Preview lancé (PID: {pid})", C_GREEN)

    def _on_preview_stopped(self):
        self._preview_running = False
        self._log_preview("■ App preview arrêtée.\n", C_GRAY)
        self._update_preview_status("○", "Arrêtée", C_GRAY)
        self.btn_preview.setEnabled(True)
        self.btn_stop_preview.setEnabled(False)

    def _on_preview_output(self, line: str):
        self._log_preview(line + "\n", C_GREEN)

    def _on_preview_crashed(self, error: str):
        self._preview_running = False
        self._log_preview(f"❌ ERREUR: {error}\n", C_RED)
        self._update_preview_status("●", "Crash !", C_RED)
        self.btn_preview.setEnabled(True)
        self.btn_stop_preview.setEnabled(False)
        self._log(f"❌ Preview crash: {error}", C_RED)

    def _update_preview_status(self, dot: str, text: str, color: str):
        self.preview_status_dot.setText(dot)
        self.preview_status_dot.setStyleSheet(f"color: {color}; font-size: 14px;")
        self.preview_status_label.setText(text)
        self.preview_status_label.setStyleSheet(f"color: {color}; font-size: 11px;")

    def _log_preview(self, text: str, color: str = C_GREEN):
        cursor = self.preview_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(text)
        self.preview_log.setTextCursor(cursor)
        self.preview_log.ensureCursorVisible()

    # ─────────────────────────────────────────────
    # Validation / Refus
    # ─────────────────────────────────────────────

    def _validate(self):
        """Accepte et applique les modifications sur l'app de base."""
        if not self._current_plan:
            return

        # Stop preview si en cours
        if self._preview_running:
            self._stop_preview()

        self.btn_validate.setEnabled(False)
        self.btn_refuse.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # Indéterminé

        self._log("✔ Application des modifications sur l'app de base…", C_GREEN)

        # Applique les modifications
        ok, msg = self.modifier.apply_plan(self._current_plan)

        self.progress.setVisible(False)

        if ok:
            # Snapshot post-modification
            if self.snapshot.available:
                hash_ = self.snapshot.create_snapshot("Post-modification IA validée")
                if hash_:
                    self._log(f"📸 Snapshot post-modification: {hash_[:8]}", C_GREEN)

            # Nettoie _preview/
            self._cleanup_preview()

            self._set_status("✅ Modifications appliquées avec succès !", C_GREEN)
            self._log(msg, C_GREEN)
            self.header.setStyleSheet(
                HEADER_STYLE + f"QLabel {{ color: {C_GREEN}; border-color: {C_GREEN}; }}"
            )

            self.modification_applied.emit()

            # Informe l'utilisateur
            self._log(
                "\n✅ Les fichiers ont été modifiés.\n"
                "   Recharge l'app (ferme et relance main.py) pour voir les changements.\n",
                C_GREEN
            )
        else:
            self._log(f"❌ Erreur lors de l'application: {msg}", C_RED)
            self.btn_validate.setEnabled(True)
            self.btn_refuse.setEnabled(True)

    def _refuse(self):
        """Refuse les modifications et rollback."""
        # Stop preview si en cours
        if self._preview_running:
            self._stop_preview()

        self._log("✘ Refus des modifications — Rollback Git…", C_RED)

        # Rollback Git si on a un snapshot
        if self._snapshot_hash and self.snapshot.available:
            ok, out = self.snapshot.rollback_to(self._snapshot_hash)
            if ok:
                self._log(
                    f"✅ Rollback vers {self._snapshot_hash[:8]} effectué",
                    C_GREEN
                )
            else:
                self._log(f"⚠ Rollback Git: {out[:100]}", C_ORANGE)

        # Nettoie _preview/
        self._cleanup_preview()

        # Reset complet
        self._set_status("○ Modifications refusées — En attente…", C_GRAY)
        self.header.setStyleSheet(
            HEADER_STYLE + f"QLabel {{ color: {C_GRAY}; border-color: {C_GRAY}; }}"
        )
        self.file_count.setText("")

        self.btn_validate.setEnabled(False)
        self.btn_refuse.setEnabled(False)
        self.btn_preview.setEnabled(False)
        self._current_plan = None
        self._snapshot_hash = None

        self.modification_refused.emit()
        self._log("🗑 Demande oubliée. En attente de la prochaine proposition.", C_GRAY)

    def _cleanup_preview(self):
        """Supprime le dossier _preview/."""
        preview_dir = os.path.join(self.modifier.base_dir, "_preview")
        if os.path.exists(preview_dir):
            try:
                shutil.rmtree(preview_dir)
                self._log("🗑 Dossier _preview/ supprimé", C_GRAY)
            except Exception as e:
                self._log(f"⚠ Impossible de supprimer _preview/: {e}", C_ORANGE)

    # ─────────────────────────────────────────────
    # Helpers UI
    # ─────────────────────────────────────────────

    def _set_status(self, text: str, color: str):
        self.status_text.setText(text)
        self.status_text.setStyleSheet(f"color: {color}; font-size: 12px;")
        self.status_icon.setStyleSheet(f"color: {color}; font-size: 16px;")

    def _log(self, text: str, color: str = C_WHITE):
        """Ajoute une ligne dans l'onglet Log."""
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(text + "\n")
        self.log_view.setTextCursor(cursor)
        self.log_view.ensureCursorVisible()
        # Propage aussi vers la fenêtre principale
        self.log_message.emit(text, color)
