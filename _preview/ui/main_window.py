"""
Fenêtre principale — Admin Console IA avec auto-modification.
Architecture:
┌─────────────────────────────────────────────────────────┐
│ ModelBar (sélection modèle, statut Ollama)              │
├──────────────────────┬──────────────────────────────────┤
│                      │                                  │
│  QTabWidget gauche   │  Panel droit (modifications)     │
│  ┌────────────────┐  │  ┌────────────────────────────┐  │
│  │  💬 Chat IA    │  │  │  Diff / Fichiers / Log     │  │
│  ├────────────────┤  │  │  [Preview] [Valider] [Non] │  │
│  │  📁 Fichiers   │  │  └────────────────────────────┘  │
│  ├────────────────┤  │                                  │
│  │  📸 Snapshots  │  │                                  │
│  └────────────────┘  │                                  │
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
# Le code va UNIQUEMENT dans le format ## FILE:
# La description courte va dans le texte normal
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
        self.file_browser.ask_ai_to_modify.connect(
            self._on_ask_ai_to_modify_file
        )
        self.left_tabs.addTab(self.file_browser, "📁 Fichiers")

        # Tab 3: Snapshots
        self.snapshot_panel = SnapshotPanel(snapshot=self.snapshot)
        self.snapshot_panel.rollback_done.connect(
            lambda msg: self._set_status(msg, C_GREEN)
        )
        self.left_tabs.addTab(self.snapshot_panel, "📸 Snapshots")

        left_layout.addWidget(self.left_tabs)
        self.main_splitter.addWidget(left_panel)

        # ── Panneau droit: Modifications ─────────
        self.modification_panel = ModificationPanel(
            modifier=self.modifier,
            snapshot=self.snapshot,
            reloader=self.reloader
        )
        self.modification_panel.log_message.connect(
            lambda msg, color: self._set_status(msg, color)
        )
        self.modification_panel.modification_applied.connect(
            self._on_modification_applied
        )
        self.modification_panel.modification_refused.connect(
            self._on_modification_refused
        )
        self.main_splitter.addWidget(self.modification_panel)

        # Ratio 60/40
        self.main_splitter.setSizes([700, 500])
        main_layout.addWidget(self.main_splitter, stretch=1)

    def _setup_status_bar(self):
        self.status_bar = self.statusBar()
        self.status_bar.setStyleSheet(STATUS_BAR_STYLE)

        self._status_label = QLabel("⚡ Prêt")
        self._status_label.setStyleSheet(
            f"color: {C_GREEN}; font-size: 11px; padding: 2px 8px;"
        )
        self.status_bar.addWidget(self._status_label)
        self.status_bar.addPermanentWidget(QLabel(" "))  # spacer

        self._model_indicator = QLabel("Modèle: –")
        self._model_indicator.setStyleSheet(
            f"color: {C_BLUE}; font-size: 11px; padding: 2px 8px;"
        )
        self.status_bar.addPermanentWidget(self._model_indicator)

        self._git_indicator = QLabel()
        if self.snapshot.available:
            self._git_indicator.setText("● Git")
            self._git_indicator.setStyleSheet(
                f"color: {C_GREEN}; font-size: 11px; padding: 2px 8px;"
            )
        else:
            self._git_indicator.setText("○ Git")
            self._git_indicator.setStyleSheet(
                f"color: {C_GRAY}; font-size: 11px; padding: 2px 8px;"
            )
        self.status_bar.addPermanentWidget(self._git_indicator)

    def _restore_geometry(self):
        """Restaure la géométrie sauvegardée."""
        geom = self.config.get("window_geometry")
        if geom:
            try:
                from PyQt6.QtCore import QByteArray
                self.restoreGeometry(QByteArray.fromHex(geom.encode()))
            except Exception:
                pass

    # ─────────────────────────────────────────────
    # Slots modèle
    # ─────────────────────────────────────────────

    def _on_model_changed(self, model: str):
        self._current_model = model
        self.config["last_model"] = model
        self._model_indicator.setText(f"Modèle: {model}")
        self._set_status(f"Modèle sélectionné: {model}", C_BLUE)

    # ─────────────────────────────────────────────
    # Slots chat
    # ─────────────────────────────────────────────

    def _on_message_sent(self, text: str):
        """L'utilisateur a envoyé un message."""
        if not self._current_model:
            self.chat_widget.show_error(
                "Aucun modèle sélectionné. Choisir un modèle d'abord."
            )
            return

        # Gestion des commandes spéciales
        if text.startswith("/"):
            self._handle_command(text)
            return

        # Démarre le streaming IA
        self._start_ai_call(text)

    def _handle_command(self, text: str):
        """Traite les commandes spéciales /cmd."""
        cmd = text.split()[0].lower()
        args = text[len(cmd):].strip()

        if cmd == "/fichiers":
            files = self.modifier.list_app_files()
            msg = "📁 Fichiers de l'app:\n" + "\n".join(f"  • {f}" for f in files)
            self.chat_widget.show_system(msg, C_GREEN)
            self.left_tabs.setCurrentIndex(1)

        elif cmd == "/snapshot":
            self._manual_snapshot()

        elif cmd == "/historique":
            self.left_tabs.setCurrentIndex(2)
            self.snapshot_panel.refresh()
            self.chat_widget.show_system("→ Onglet Snapshots ouvert", C_GREEN)

        elif cmd == "/modifier":
            if args:
                content = self.modifier.get_file_content(args)
                if content:
                    self._on_ask_ai_to_modify_file(args, content)
                else:
                    self.chat_widget.show_system(
                        f"❌ Fichier introuvable: {args}", C_RED
                    )
            else:
                self.chat_widget.show_system(
                    "Usage: /modifier chemin/du/fichier.py", C_YELLOW
                )

        elif cmd == "/aide":
            aide = (
                "Commandes disponibles:\n"
                "  /fichiers  — Liste tous les fichiers\n"
                "  /modifier  — Demander à l'IA de modifier un fichier\n"
                "  /snapshot  — Créer un snapshot Git maintenant\n"
                "  /historique — Voir l'historique des snapshots\n"
                "  /aide      — Cette aide\n\n"
                "Pour demander une modification:\n"
                "  Dis à l'IA: 'Modifie ui/styles.py pour mettre le fond en blanc'\n"
                "  → L'IA décrit ce qu'elle va faire dans le chat\n"
                "  → Le code modifié apparaît AUTOMATIQUEMENT dans le panneau droit\n"
                "  → Clique [✔ VALIDER] pour appliquer ou [✘ REFUSER] pour annuler\n"
            )
            self.chat_widget.show_system(aide, C_GREEN)

        else:
            self.chat_widget.show_system(
                f"Commande inconnue: {cmd}. Tape /aide pour l'aide.", C_RED
            )

    def _start_ai_call(self, user_message: str):
        """Lance un appel IA en streaming."""
        if not self._current_model:
            return

        # Stoppe un worker précédent
        if self._current_worker and self._current_worker.isRunning():
            self._current_worker.stop()
            self._current_worker.wait(2000)

        history = self.chat_widget.get_history()
        self.chat_widget.start_ai_response()
        self._set_status(f"⚙ IA en cours… ({self._current_model})", C_YELLOW)

        self._current_worker = OllamaWorker(
            model=self._current_model,
            messages=history,
            ollama_url=self.config.get("ollama_url", "http://localhost:11434"),
            system_prompt=SYSTEM_PROMPT
        )
        self._current_worker.token_received.connect(
            self.chat_widget.append_token
        )
        self._current_worker.response_done.connect(self._on_response_done)
        self._current_worker.error_occurred.connect(self._on_response_error)
        self._current_worker.start()

    def _on_response_done(self, full_text: str):
        """Réponse IA complète reçue."""
        self.chat_widget.finish_ai_response()
        self.chat_widget.add_to_history("assistant", full_text)
        self._set_status("✅ Réponse reçue", C_GREEN)

    def _on_response_error(self, error: str):
        """Erreur lors de l'appel IA."""
        self.chat_widget.show_error(error)
        self._set_status(f"❌ Erreur: {error[:50]}", C_RED)

    def _on_stop_requested(self):
        """L'utilisateur veut stopper le streaming."""
        if self._current_worker and self._current_worker.isRunning():
            self._current_worker.stop()
            self.chat_widget.finish_ai_response()
            self._set_status("⏹ Arrêté par l'utilisateur", C_ORANGE)

    # ─────────────────────────────────────────────
    # Slots modifications de code
    # ─────────────────────────────────────────────

    def _on_code_proposed(self, ai_response: str):
        """
        L'IA a proposé une modification de code.
        → On charge le plan dans le panneau DROIT directement.
        → On NE réaffiche PAS le code dans le chat.
        """
        self._set_status("🔧 Analyse du code proposé…", C_YELLOW)
        plan = self.modifier.build_modification_plan(ai_response)

        if plan.is_valid:
            # Charge et affiche dans le panneau droit
            self.modification_panel.load_plan(plan)

            # Message court dans le chat (pas le code)
            nb = len(plan.blocks)
            fichiers = ", ".join(b.filename for b in plan.blocks)
            self.chat_widget.show_system(
                f"🔧 {nb} fichier(s) prêt(s) à modifier : {fichiers}\n"
                f"   → Voir panneau DROIT pour valider ou refuser.",
                C_YELLOW
            )

            self._set_status(
                f"🔧 {nb} modification(s) en attente — panneau droit",
                C_YELLOW
            )

            # Flash visuel sur le panneau droit pour attirer l'attention
            self._flash_modification_panel()

        else:
            errors = "; ".join(plan.validation_errors[:2])
            self.chat_widget.show_system(
                f"⚠️ La réponse IA ne contient pas de code valide:\n{errors}\n"
                "Essaie: 'Utilise le format ## FILE: nom.py pour ta réponse.'",
                C_ORANGE
            )
            self._set_status("⚠️ Aucun code valide détecté", C_ORANGE)

    def _flash_modification_panel(self):
        """
        Fait clignoter le panneau droit 3 fois pour signaler
        qu'une modification est disponible.
        """
        original_style = self.main_splitter.styleSheet()
        flash_style = (
            f"QSplitter::handle {{ background: {C_YELLOW}; width: 4px; }}"
        )

        count = [0]

        def toggle():
            if count[0] % 2 == 0:
                self.main_splitter.setStyleSheet(flash_style)
            else:
                self.main_splitter.setStyleSheet(
                    f"QSplitter::handle {{ background: {C_GRAY}; }}"
                )
            count[0] += 1
            if count[0] >= 6:
                timer.stop()
                self.main_splitter.setStyleSheet(
                    f"QSplitter::handle {{ background: {C_GRAY}; }}"
                )

        timer = QTimer(self)
        timer.timeout.connect(toggle)
        timer.start(200)

    def _on_ask_ai_to_modify_file(self, filename: str, content: str):
        """
        Pré-remplit le chat avec une demande de modification d'un fichier.
        """
        prompt = (
            f"Voici le contenu actuel du fichier `{filename}`:\n\n"
            f"## FILE: {filename}\n"
            f"```python\n{content[:3000]}"
            f"{'...(tronqué)' if len(content) > 3000 else ''}\n```\n\n"
            f"[Décris ici ce que tu veux modifier dans ce fichier]"
        )
        self.chat_widget.input_box.setPlainText(
            f"Modifie le fichier `{filename}` pour: "
        )
        self.chat_widget.input_box.setFocus()
        self.left_tabs.setCurrentIndex(0)  # Revient au chat

        # Ajoute le contenu du fichier dans l'historique (contexte pour l'IA)
        self.chat_widget.add_to_history("user", prompt)
        self.chat_widget.show_system(
            f"📎 Fichier '{filename}' chargé en contexte.\n"
            "Décris ta modification dans la zone de saisie.",
            C_BLUE
        )

    def _on_modification_applied(self):
        """La modification a été appliquée sur l'app de base."""
        self.chat_widget.show_system(
            "✅ Modifications appliquées sur l'app de base. Rechargement en cours…",
            C_GREEN
        )
        self.file_browser.refresh()
        self.snapshot_panel.refresh()

    def _on_modification_refused(self):
        """La modification a été refusée."""
        self.chat_widget.show_system(
            "✘ Modifications refusées. Rollback effectué.", C_RED
        )

    # ─────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────

    def _manual_snapshot(self):
        if not self.snapshot.available:
            self._set_status("⚠️ Git non disponible", C_ORANGE)
            return
        hash_ = self.snapshot.create_snapshot("Manuel via menu")
        if hash_:
            self._set_status(f"📸 Snapshot créé: {hash_[:8]}", C_GREEN)
            self.snapshot_panel.refresh()

    def _set_status(self, msg: str, color: str = C_GREEN):
        """Met à jour la barre de statut."""
        self._status_label.setText(msg)
        self._status_label.setStyleSheet(
            f"color: {color}; font-size: 11px; padding: 2px 8px;"
        )

    def _show_about(self):
        QMessageBox.information(
            self,
            "À propos",
            "Admin Console — IA Locale v2.0\n\n"
            "Interface d'administration IA avec:\n"
            "• Chat en streaming avec Ollama\n"
            "• Détection automatique des modèles\n"
            "• Auto-modification de code par l'IA\n"
            "• Preview isolé avant validation\n"
            "• Snapshots Git automatiques\n"
            "• Rollback en cas de problème\n\n"
            "Stack: Python · PyQt6 · Ollama · Git"
        )

    # ─────────────────────────────────────────────
    # Cycle de vie
    # ─────────────────────────────────────────────

    def closeEvent(self, event):
        """Sauvegarde et nettoyage avant fermeture."""
        # Sauvegarde la géométrie
        self.config["window_geometry"] = (
            self.saveGeometry().toHex().data().decode()
        )
        self.config["last_model"] = self._current_model

        # Arrête les workers
        if self._current_worker and self._current_worker.isRunning():
            self._current_worker.stop()
            self._current_worker.wait(2000)

        # Arrête les processus preview
        self.reloader.cleanup()

        # Sauvegarde la config
        self.save_callback(self.config)
        event.accept()
