"""
Gestionnaire de lancement/rechargement de l'app preview et de l'app de base.
- Lance l'app preview dans un sous-processus isolé
- Tue le sous-processus en cas de refus
- Relance l'app de base après validation
"""

import os
import sys
import subprocess
import signal
from typing import Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal, QTimer


class AppProcess(QThread):
    """Thread qui surveille un sous-processus d'app."""

    process_started = pyqtSignal(int)       # PID
    process_stopped = pyqtSignal(int)       # code de retour
    process_output = pyqtSignal(str)        # stdout/stderr
    process_crashed = pyqtSignal(str)       # message d'erreur

    def __init__(self, script_path: str, cwd: str, label: str = "", parent=None):
        super().__init__(parent)
        self.script_path = script_path
        self.cwd = cwd
        self.label = label
        self._process: Optional[subprocess.Popen] = None
        self._stop_requested = False

    def run(self):
        """Lance le sous-processus et lit sa sortie."""
        self._stop_requested = False
        try:
            self._process = subprocess.Popen(
                [sys.executable, self.script_path],
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            self.process_started.emit(self._process.pid)

            # Lit la sortie ligne par ligne
            for line in self._process.stdout:
                if self._stop_requested:
                    break
                self.process_output.emit(f"[{self.label}] {line.rstrip()}")

            ret = self._process.wait()
            if not self._stop_requested:
                if ret != 0:
                    self.process_crashed.emit(
                        f"App terminée avec code {ret}"
                    )
                else:
                    self.process_stopped.emit(ret)

        except Exception as e:
            self.process_crashed.emit(str(e))

    def stop(self):
        """Arrête proprement le sous-processus."""
        self._stop_requested = True
        if self._process and self._process.poll() is None:
            try:
                # Windows : terminate, Unix : SIGTERM
                self._process.terminate()
                try:
                    self._process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self._process.kill()
            except Exception:
                pass


class AppReloader(QObject):
    """
    Orchestre :
    1. Le lancement de l'app preview (dans _preview/)
    2. Le kill de l'app preview
    3. Le rechargement de l'app de base après validation
    """

    # Signaux
    preview_launched = pyqtSignal(int)      # PID preview
    preview_stopped = pyqtSignal()
    preview_output = pyqtSignal(str)
    preview_crashed = pyqtSignal(str)

    base_launched = pyqtSignal(int)         # PID base (relancée)
    base_output = pyqtSignal(str)

    status_changed = pyqtSignal(str)        # Message de statut

    def __init__(self, base_dir: str, parent=None):
        super().__init__(parent)
        self.base_dir = base_dir
        self.preview_dir = os.path.join(base_dir, "_preview")
        self._preview_process: Optional[AppProcess] = None
        self._base_process: Optional[AppProcess] = None
        self._restart_timer: Optional[QTimer] = None

    # ─────────────────────────────────────────────
    # Preview
    # ─────────────────────────────────────────────

    def launch_preview(self):
        """Lance l'app depuis _preview/ dans un process séparé."""
        # Stoppe un preview existant
        self.stop_preview()

        main_script = os.path.join(self.preview_dir, "main.py")
        if not os.path.exists(main_script):
            self.status_changed.emit(
                "❌ main.py introuvable dans _preview/"
            )
            return

        self._preview_process = AppProcess(
            script_path=main_script,
            cwd=self.preview_dir,
            label="PREVIEW",
            parent=None
        )
        self._preview_process.process_started.connect(self.preview_launched)
        self._preview_process.process_stopped.connect(
            lambda _: self.preview_stopped.emit()
        )
        self._preview_process.process_output.connect(self.preview_output)
        self._preview_process.process_crashed.connect(self.preview_crashed)

        self._preview_process.start()
        self.status_changed.emit("🟢 Preview lancé")

    def stop_preview(self):
        """Arrête l'app preview."""
        if self._preview_process and self._preview_process.isRunning():
            self._preview_process.stop()
            self._preview_process.wait(3000)
            self._preview_process = None
            self.status_changed.emit("🔴 Preview arrêté")

    def is_preview_running(self) -> bool:
        return (
            self._preview_process is not None and
            self._preview_process.isRunning()
        )

    # ─────────────────────────────────────────────
    # Rechargement app de base
    # ─────────────────────────────────────────────

    def restart_base_app(self, delay_ms: int = 1500):
        """
        Relance l'app de base depuis base_dir.
        L'app courante (Admin Console) reste ouverte.
        """
        main_script = os.path.join(self.base_dir, "main.py")
        if not os.path.exists(main_script):
            self.status_changed.emit("❌ main.py introuvable dans base_dir")
            return

        # Stoppe un process de base existant
        if self._base_process and self._base_process.isRunning():
            self._base_process.stop()

        def do_restart():
            self._base_process = AppProcess(
                script_path=main_script,
                cwd=self.base_dir,
                label="BASE",
                parent=None
            )
            self._base_process.process_started.connect(self.base_launched)
            self._base_process.process_output.connect(self.base_output)
            self._base_process.start()
            self.status_changed.emit(
                f"✅ App de base rechargée (PID {self._base_process._process.pid if self._base_process._process else '?'})"
            )

        # Petit délai pour que les fichiers soient bien écrits
        self._restart_timer = QTimer()
        self._restart_timer.setSingleShot(True)
        self._restart_timer.timeout.connect(do_restart)
        self._restart_timer.start(delay_ms)

    def cleanup(self):
        """Arrête tous les sous-processus."""
        self.stop_preview()
        if self._base_process and self._base_process.isRunning():
            self._base_process.stop()
