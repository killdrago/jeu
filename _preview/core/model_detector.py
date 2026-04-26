"""
Détection automatique des modèles Ollama disponibles.
Scanne aussi le dossier ./model/ pour les fichiers .gguf locaux.
"""

import os
import glob
import requests
from typing import List, Optional


class ModelDetector:
    """Détecte les modèles disponibles via Ollama API et en local."""

    def __init__(self, ollama_url: str = "http://localhost:11434", base_dir: str = "."):
        self.ollama_url = ollama_url.rstrip("/")
        self.base_dir = base_dir
        self.model_dir = os.path.join(base_dir, "model")

    def detect_ollama_models(self) -> List[str]:
        """Retourne la liste des modèles disponibles sur Ollama."""
        try:
            resp = requests.get(
                f"{self.ollama_url}/api/tags",
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                return sorted(models)
        except requests.exceptions.ConnectionError:
            pass
        except Exception as e:
            print(f"[ModelDetector] Erreur: {e}")
        return []

    def detect_local_gguf(self) -> List[str]:
        """Scanne le dossier ./model/ pour les fichiers .gguf."""
        if not os.path.exists(self.model_dir):
            return []
        pattern = os.path.join(self.model_dir, "*.gguf")
        files = glob.glob(pattern)
        return [os.path.basename(f) for f in files]

    def get_best_model(self) -> Optional[str]:
        """Retourne le premier modèle disponible (Ollama en priorité)."""
        models = self.detect_ollama_models()
        if models:
            return models[0]
        return None

    def is_ollama_running(self) -> bool:
        """Vérifie si Ollama est lancé."""
        try:
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def get_model_info(self, model_name: str) -> Optional[dict]:
        """Retourne les infos d'un modèle Ollama."""
        try:
            resp = requests.post(
                f"{self.ollama_url}/api/show",
                json={"name": model_name},
                timeout=5
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None
