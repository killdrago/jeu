"""
Fenêtre principale — Admin Console IA avec auto-modification.
Architecture:
┌─────────────────────────────────────────────────────────┐
│ ModelBar (sélection modèle, statut Ollama)              │
├──────────────────────┬──────────────────────────────────┤
│                      │                                  │
│  QTabWidget gauche   │  Panel droit (modifications)     │
│  ┌────────────────┐  │  ┌────────────────────────────┐  │
│  │  💬 Chat IA    │  │  │  Onglet: Δ Diff             │  │
│  ├────────────────┤  │  │  Onglet: { } Code          │  │
│  │  📁 Fichiers   │  │  │    ├ Liste fichiers modif.  │  │
│  ├────────────────┤  │  │    └ Code avec surbrillance │  │
│  │  📸 Snapshots  │  │  │  Onglet: 🖥 Preview         │  │
│  └────────────────┘  │  │  Onglet: 📋 Log             │  │
│                      │  │                              │  │
│                      │  │  [▶ TESTER] [■ STOP]        │  │
│                      │  │  [✔ ACCEPTER] [✘ REFUSER]   │  │
│                      │  └────────────────────────────┘  │
├──────────────────────┴──────────────────────────────────┤
│ StatusBar (modèle actif, statut, messages)              │
└─────────────────────────────────────────────────────────┘
"""

import os
from typing import Callable, Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTabWidget, QStatusBar, QLabel,
    QMenuBar, QMenu, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence, QColor

from ui.styles import *
from ui.model_bar import ModelBar
from ui.chat_widget import ChatWidget
from ui.modification_panel import ModificationPanel
from ui.file_browser import FileBrowser
from ui.snapshot_panel import SnapshotPanel
from core.model_detector import ModelDetector
from core.ollama_worker import OllamaWorker
from core.code_modifier import CodeModifier
from core.git_snapshot import GitSnapshot
from core.app_reloader import AppReloader

# ─────────────────────────────────────────────────────────
# Prompt système — l'IA sépare la description du code
# ─────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Tu es un assistant IA intégré dans une "Admin Console" — un outil d'administration Python/PyQt6.

Quand on te demande de modifier un fichier de l'application, réponds TOUJOURS en deux parties distinctes :

PARTIE 1 — Description courte (2-3 lignes max, en français) :
Explique brièvement CE QUE tu vas changer, sans montrer de code ici.
Ex : "Je vais modifier ui/styles.py pour changer la couleur de fond de noir (#0a0a0a) en blanc (#ffffff)."

PARTIE 2 — Le code modifié, OBLIGATOIREMENT dans ce format exact :

## FILE: chemin/relatif/du/fichier.py
```python
# code complet du fichier ici
```

RÈGLES IMPORTANTES :
- Ne mets JAMAIS le code dans le texte de description, seulement dans les blocs ## FILE:
- Donne TOUJOURS le fichier COMPLET, pas juste les lignes modifiées
- Tu peux modifier plusieurs fichiers : utilise plusieurs blocs ## FILE:
- Assure-toi que le Python est syntaxiquement correct
- Conserve tous les imports existants

Si on ne te demande PAS de modifier du code, réponds normalement en français, sans bloc ## FILE:.
"""


class MainWindow(QMainWindow):
    """Fenêtre principale de l'Admin Console."""

    def __init__(self, config: dict, save_callback: Callable, base_dir: str):
        super().__init__()
        self.config = config
        self.save_callback = save_callback
        self.base_dir = base_dir

        # Composants core
        self.detector = ModelDetector(
            ollama_url=config.get("ollama_url", "http://localhost:11434"),
            base_dir=base_dir
        )
        self.modifier = CodeModifier(base_dir=base_dir)
        self.snapshot = GitSnapshot(base_dir=base_dir)
        self.reloader = AppReloader(base_dir=base_dir)

        # État
        self._current_model: str = config.get("last_model", "")
        self._current_worker: Optional[OllamaWorker] = None

        self._setup_window()
        self._setup_menu()
        self._setup_ui()
        self._setup_status_bar()
        self._restore_geometry()

    # ─────────────────────────────────────────────
    # Setup fenêtre
    # ─────────────────────────────────────────────

    def _setup_window(self):
        self.setWindowTitle("Admin Console — IA Locale v2.0")
        self.setMinimumSize(1100, 700)
        self.resize(1400, 850)
        self.setStyleSheet(MAIN_STYLE)

    def _setup_menu(self):
        menubar = self.menuBar()
        menubar.setStyleSheet(f"""
            QMenuBar {{
                background: {C_BG2};
                color: {C_GREEN};
                border-bottom: 1px solid {C_GRAY};
                font-family: {FONT_MONO};
                font-size: 12px;
            }}
            QMenuBar::item:selected {{ background: {C_GRAY2}; }}
            QMenu {{
                background: {C_BG2};
                color: {C_GREEN};
                border: 1px solid {C_GRAY};
                font-family: {FONT_MONO};
            }}
            QMenu::item:selected {{ background: {C_GRAY2}; }}
        """)

        # Menu Fichier
        file_menu = menubar.addMenu("Fichier")
        action_snapshot = QAction("📸 Créer un snapshot", self)
        action_snapshot.setShortcut(QKeySequence("Ctrl+S"))
        action_snapshot.triggered.connect(self._manual_snapshot)
        file_menu.addAction(action_snapshot)
        file_menu.addSeparator()
        action_quit = QAction("Quitter", self)
        action_quit.setShortcut(QKeySequence("Ctrl+Q"))
        action_quit.triggered.connect(self.close)
        file_menu.addAction(action_quit)

        # Menu IA
        ia_menu = menubar.addMenu("IA")
        action_clear = QAction("🗑 Effacer le chat", self)
        action_clear.setShortcut(QKeySequence("Ctrl+L"))
        action_clear.triggered.connect(
            lambda: self.chat_widget.display.clear()
        )
        ia_menu.addAction(action_clear)
        action_refresh_models = QAction("↺ Rafraîchir les modèles", self)
        action_refresh_models.triggered.connect(
            lambda: self.model_bar._auto_detect()
        )
        ia_menu.addAction(action_refresh_models)

        # Menu Aide
        help_menu = menubar.addMenu("Aide")
        action_about = QAction("À propos", self)
        action_about.triggered.connect(self._show_about)
        help_menu.addAction(action_about)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── ModelBar ────────────────────────────
        self.model_bar = ModelBar(
            detector=self.detector,
            last_model=self._current_model
        )
        self.model_bar.model_changed.connect(self._on_model_changed)
        self.model_bar.status_updated.connect(
            lambda msg, color: self._set_status(msg, color)
        )
        main_layout.addWidget(self.model_bar)

        # ── Splitter principal ───────────────────
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setHandleWidth(3)
        self.main_splitter.setStyleSheet(
            f"QSplitter::handle {{ background: {C_GRAY}; }}"
        )

        # ── Panneau gauche: Tabs ─────────────────
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self.left_tabs = QTabWidget()
        self.left_tabs.setStyleSheet(TAB_STYLE)

        # Tab 1: Chat IA
        self.chat_widget = ChatWidget()
        self.chat_widget.message_sent.connect(self._on_message_sent)
        self.chat_widget.stop_requested.connect(self._on_stop_requested)
        self.chat_widget.code_modification_proposed.connect(
            self._on_code_proposed
        )
        self.left_tabs.addTab(self.chat_widget, "💬 Chat IA")

        # Tab 2: Navigateur de fichiers
        self.file_browser = FileBrowser(base_dir=self.base_dir)
        self.file_browser.ask_ai_to_modify.connect(self._on_ask_ai_to_modify)
        self.left_tabs.addTab(self.file_browser, "📁 Fichiers")

        # Tab 3: Snapshots
        self.snapshot_panel = SnapshotPanel(snapshot=self.snapshot)
        self.snapshot_panel.rollback_done.connect(
            lambda msg: self._set_status(msg, C_BLUE)
        )
        self.left_tabs.addTab(self.snapshot_panel, "📸 Snapshots")

        left_layout.addWidget(self.left_tabs)
        self.main_splitter.addWidget(left_panel)

        # ── Panneau droit: Modification Panel ───
        self.mod_panel = ModificationPanel(
            modifier=self.modifier,
            snapshot=self.snapshot,
            reloader=self.reloader
        )
        self.mod_panel.log_message.connect(
            lambda msg, color: self._set_status(msg, color)
        )
        self.mod_panel.modification_applied.connect(self._on_modification_applied)
        self.mod_panel.modification_refused.connect(self._on_modification_refused)
        self.main_splitter.addWidget(self.mod_panel)

        # Tailles initiales: 55% gauche, 45% droite
        self.main_splitter.setSizes([600, 500])

        main_layout.addWidget(self.main_splitter, stretch=1)

    def _setup_status_bar(self):
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet(STATUS_BAR_STYLE)
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel("Prêt")
        self.status_label.setStyleSheet(f"color: {C_GREEN_DIM}; font-size: 11px;")
        self.status_bar.addWidget(self.status_label)

        self.status_bar.addPermanentWidget(QLabel(""))

        self.model_label = QLabel("Aucun modèle")
        self.model_label.setStyleSheet(f"color: {C_GRAY}; font-size: 11px;")
        self.status_bar.addPermanentWidget(self.model_label)

    def _restore_geometry(self):
        geom = self.config.get("window_geometry")
        if geom and isinstance(geom, list) and len(geom) == 4:
            self.setGeometry(*geom)

    # ─────────────────────────────────────────────
    # Slots
    # ─────────────────────────────────────────────

    def _on_model_changed(self, model: str):
        self._current_model = model
        self.model_label.setText(f"⬡ {model}")
        self.config["last_model"] = model
        self.save_callback(self.config)
        self._set_status(f"Modèle sélectionné: {model}", C_GREEN)

    def _on_message_sent(self, message: str):
        """L'utilisateur envoie un message → lance le worker Ollama."""
        if not self._current_model:
            self._set_status("❌ Aucun modèle sélectionné", C_RED)
            self.chat_widget.add_error("Sélectionne d'abord un modèle !")
            return

        # Construit l'historique
        history = self.chat_widget.get_history()
        history.append({"role": "user", "content": message})

        # Lance le worker
        self._current_worker = OllamaWorker(
            model=self._current_model,
            messages=history,
            ollama_url=self.config.get("ollama_url", "http://localhost:11434"),
            system_prompt=SYSTEM_PROMPT
        )
        self._current_worker.token_received.connect(
            self.chat_widget.append_ai_token
        )
        self._current_worker.response_done.connect(self._on_response_done)
        self._current_worker.error_occurred.connect(self._on_worker_error)
        self._current_worker.thinking_started.connect(
            self.chat_widget.start_ai_response
        )
        self._current_worker.start()

        self._set_status(f"⟳ Génération en cours…", C_YELLOW)

    def _on_response_done(self, full_response: str):
        """L'IA a fini de répondre."""
        self.chat_widget.finish_ai_response(full_response)
        self._set_status("✓ Réponse reçue", C_GREEN)

        # Vérifie si la réponse contient du code à modifier
        blocks = self.modifier.extract_code_blocks(full_response)
        if blocks:
            self._set_status(
                f"🔧 {len(blocks)} fichier(s) à modifier détecté(s) → panneau droit",
                C_YELLOW
            )
            # Active automatiquement le panneau de modification
            self._on_code_proposed(full_response)

    def _on_code_proposed(self, ai_response: str):
        """L'IA propose une modification de code → active le panel droit."""
        self.mod_panel.propose_modification(ai_response)

    def _on_worker_error(self, error: str):
        self.chat_widget.add_error(error)
        self._set_status(f"❌ Erreur: {error[:60]}", C_RED)

    def _on_stop_requested(self):
        if self._current_worker and self._current_worker.isRunning():
            self._current_worker.stop()
            self.chat_widget.finish_ai_response("")
            self._set_status("■ Génération arrêtée", C_ORANGE)

    def _on_ask_ai_to_modify(self, filename: str, content: str):
        """L'utilisateur demande à l'IA de modifier un fichier depuis l'onglet Fichiers."""
        prompt = (
            f"Voici le contenu du fichier `{filename}`:\n\n"
            f"```python\n{content[:3000]}\n```\n\n"
            f"Que veux-tu que je modifie dans ce fichier ?"
        )
        self.chat_widget.set_input(prompt)
        self.left_tabs.setCurrentIndex(0)  # Bascule sur le chat

    def _on_modification_applied(self):
        self._set_status("✅ Modifications appliquées avec succès !", C_GREEN)
        self.snapshot_panel.refresh()
        self.file_browser.refresh()

    def _on_modification_refused(self):
        self._set_status("✘ Modifications refusées — Aucun changement effectué", C_GRAY)

    def _manual_snapshot(self):
        if self.snapshot.available:
            hash_ = self.snapshot.create_snapshot("Manuel")
            if hash_:
                self._set_status(f"📸 Snapshot créé: {hash_[:8]}", C_GREEN)
                self.snapshot_panel.refresh()
        else:
            self._set_status("⚠ Git non disponible pour les snapshots", C_ORANGE)

    def _set_status(self, msg: str, color: str = C_GREEN):
        self.status_label.setText(msg)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 11px;")

    def _show_about(self):
        QMessageBox.about(
            self,
            "À propos — Admin Console IA",
            "Admin Console — IA Locale v2.0\n\n"
            "Interface d'administration avec auto-modification par l'IA.\n\n"
            "Stack: Python 3.10+ / PyQt6 / Ollama\n\n"
            "Workflow:\n"
            "  1. Demande une modif à l'IA dans le chat\n"
            "  2. Le code modifié apparaît dans le panneau droit\n"
            "  3. Onglet 'Code' → voir les lignes modifiées (surbrillance)\n"
            "  4. Bouton TESTER → lance l'app modifiée\n"
            "  5. ACCEPTER → applique | REFUSER → rollback\n"
        )

    # ─────────────────────────────────────────────
    # Fermeture
    # ─────────────────────────────────────────────

    def closeEvent(self, event):
        # Sauvegarde la géométrie
        geom = self.geometry()
        self.config["window_geometry"] = [geom.x(), geom.y(), geom.width(), geom.height()]
        self.save_callback(self.config)

        # Nettoie les sous-processus
        self.reloader.cleanup()

        event.accept()
