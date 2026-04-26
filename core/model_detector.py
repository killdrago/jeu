"""
=======================================================
  ADMIN CONSOLE IA — Détecteur de modèle automatique
=======================================================
  - Contacte Ollama sur localhost:11434
  - Récupère la liste des modèles disponibles
  - Retourne le premier trouvé (celui que tu as pull/importé)
  - Tourne dans un QThread pour ne pas geler l'UI
=======================================================
"""

import requests
from PyQt6.QtCore import QThread, pyqtSignal

OLLAMA_URL = "http://localhost:11434"


class ModelDetector(QThread):
    model_found     = pyqtSignal(str, str)   # (nom, taille)
    model_not_found = pyqtSignal(str)         # (message d'erreur)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            response = requests.get(
                f"{OLLAMA_URL}/api/tags",
                timeout=5
            )
            response.raise_for_status()
            data = response.json()
            models = data.get("models", [])

            if not models:
                self.model_not_found.emit(
                    "Ollama est joignable mais aucun modèle n'est installé.\n"
                    "Importez votre modèle : ollama pull llama3.2"
                )
                return

            # On prend le premier modèle disponible
            first = models[0]
            name = first.get("name", "inconnu")
            size_bytes = first.get("size", 0)
            size_str = f"{size_bytes / 1e9:.1f} GB" if size_bytes else "taille inconnue"

            self.model_found.emit(name, size_str)

        except requests.exceptions.ConnectionError:
            self.model_not_found.emit(
                "Impossible de contacter Ollama. Lancez : ollama serve"
            )
        except requests.exceptions.Timeout:
            self.model_not_found.emit(
                "Ollama ne répond pas (timeout 5s). Vérifiez qu'il est lancé."
            )
        except Exception as e:
            self.model_not_found.emit(f"Erreur inattendue : {e}")
