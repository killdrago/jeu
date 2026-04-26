"""
Gestion des snapshots Git avant toute modification de code.
Permet le rollback automatique si la validation est refusée.
"""

import os
import subprocess
import datetime
from typing import Optional, List, Tuple


class GitSnapshot:
    """Gère les snapshots Git pour sécuriser les modifications."""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self._git_available = self._check_git()
        self._repo_initialized = False

        if self._git_available:
            self._ensure_repo()

    def _check_git(self) -> bool:
        """Vérifie si Git est disponible."""
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def _run_git(self, *args) -> Tuple[bool, str]:
        """Exécute une commande Git dans base_dir."""
        try:
            result = subprocess.run(
                ["git"] + list(args),
                capture_output=True,
                text=True,
                cwd=self.base_dir,
                timeout=30
            )
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)

    def _ensure_repo(self):
        """Initialise le dépôt Git si nécessaire."""
        git_dir = os.path.join(self.base_dir, ".git")
        if not os.path.exists(git_dir):
            ok, out = self._run_git("init")
            if ok:
                self._run_git("config", "user.email", "admin-ia@local")
                self._run_git("config", "user.name", "Admin IA")
                # Gitignore de base
                gitignore = os.path.join(self.base_dir, ".gitignore")
                if not os.path.exists(gitignore):
                    with open(gitignore, "w") as f:
                        f.write("__pycache__/\n*.pyc\n*.pyo\n.env\n")
                self._run_git("add", "-A")
                self._run_git(
                    "commit", "-m",
                    "🚀 Initial snapshot — Admin Console IA"
                )
                self._repo_initialized = True
        else:
            self._repo_initialized = True

    def create_snapshot(self, label: str = "") -> Optional[str]:
        """
        Crée un snapshot Git de l'état actuel.
        Retourne le hash du commit ou None si échec.
        """
        if not self._git_available or not self._repo_initialized:
            return None

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        msg = f"[SNAPSHOT] {timestamp}"
        if label:
            msg += f" — {label}"

        self._run_git("add", "-A")
        ok, out = self._run_git("commit", "-m", msg)

        if ok:
            # Récupère le hash du commit
            ok2, hash_out = self._run_git("rev-parse", "HEAD")
            if ok2:
                return hash_out.strip()
        else:
            # Rien à committer, retourne quand même le HEAD
            ok2, hash_out = self._run_git("rev-parse", "HEAD")
            if ok2:
                return hash_out.strip()

        return None

    def rollback_to(self, commit_hash: str) -> Tuple[bool, str]:
        """Revient à un snapshot précédent (hard reset)."""
        if not self._git_available or not self._repo_initialized:
            return False, "Git non disponible"

        ok, out = self._run_git("reset", "--hard", commit_hash)
        return ok, out

    def get_diff_since(self, commit_hash: str) -> str:
        """Retourne le diff depuis un commit donné."""
        if not self._git_available:
            return ""
        _, diff = self._run_git("diff", commit_hash, "HEAD")
        return diff

    def get_history(self, n: int = 10) -> List[dict]:
        """Retourne les N derniers commits."""
        if not self._git_available:
            return []
        ok, out = self._run_git(
            "log", f"-{n}",
            "--pretty=format:%H|%s|%ai"
        )
        if not ok:
            return []
        history = []
        for line in out.strip().split("\n"):
            if "|" in line:
                parts = line.split("|", 2)
                history.append({
                    "hash": parts[0][:8],
                    "full_hash": parts[0],
                    "message": parts[1],
                    "date": parts[2] if len(parts) > 2 else ""
                })
        return history

    @property
    def available(self) -> bool:
        return self._git_available and self._repo_initialized
