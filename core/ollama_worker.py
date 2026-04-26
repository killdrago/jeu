"""
=======================================================
  ADMIN CONSOLE IA — Worker Ollama (QThread)
=======================================================
  - Envoie le message à Ollama en mode streaming
  - Émet chaque token reçu via le signal token_received
  - Tourne dans un QThread séparé → JAMAIS de freeze UI
  - Supporte l'arrêt propre via stop()
=======================================================
"""

import json
import requests
from PyQt6.QtCore import QThread, pyqtSignal

OLLAMA_URL = "http://localhost:11434"


class OllamaWorker(QThread):
    token_received  = pyqtSignal(str)   # un morceau de réponse
    finished        = pyqtSignal()      # fin normale
    error_occurred  = pyqtSignal(str)   # message d'erreur

    def __init__(self, model: str, prompt: str, history: list = None, parent=None):
        super().__init__(parent)
        self._model = model
        self._prompt = prompt
        self._history = history or []
        self._stop_flag = False

    def stop(self):
        """Demande l'arrêt propre du streaming."""
        self._stop_flag = True

    def run(self):
        try:
            # Construction de l'historique de messages
            messages = []
            for msg in self._history:
                messages.append({"role": msg["role"], "content": msg["content"]})
            messages.append({"role": "user", "content": self._prompt})

            payload = {
                "model": self._model,
                "messages": messages,
                "stream": True,
            }

            with requests.post(
                f"{OLLAMA_URL}/api/chat",
                json=payload,
                stream=True,
                timeout=120
            ) as response:
                response.raise_for_status()

                for raw_line in response.iter_lines():
                    if self._stop_flag:
                        break
                    if not raw_line:
                        continue

                    try:
                        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            self.token_received.emit(content)
                    except json.JSONDecodeError:
                        continue

            self.finished.emit()

        except requests.exceptions.ConnectionError:
            self.error_occurred.emit(
                "Connexion perdue avec Ollama. Vérifiez : ollama serve"
            )
        except requests.exceptions.Timeout:
            self.error_occurred.emit(
                "Ollama a mis trop de temps à répondre (timeout 120s)."
            )
        except Exception as e:
            self.error_occurred.emit(str(e))
