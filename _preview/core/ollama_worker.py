"""
Worker QThread pour les appels à l'API Ollama en streaming.
Ne bloque JAMAIS le thread UI.
"""

import json
import requests
from typing import List, Dict, Optional

from PyQt6.QtCore import QThread, pyqtSignal


class OllamaWorker(QThread):
    """Thread dédié aux appels Ollama avec streaming."""

    # Signaux émis vers le thread UI
    token_received = pyqtSignal(str)        # Chaque token reçu
    response_done = pyqtSignal(str)         # Réponse complète terminée
    error_occurred = pyqtSignal(str)        # Erreur survenue
    thinking_started = pyqtSignal()         # L'IA commence à réfléchir

    def __init__(
        self,
        model: str,
        messages: List[Dict[str, str]],
        ollama_url: str = "http://localhost:11434",
        system_prompt: str = "",
        parent=None
    ):
        super().__init__(parent)
        self.model = model
        self.messages = messages
        self.ollama_url = ollama_url.rstrip("/")
        self.system_prompt = system_prompt
        self._stop_requested = False
        self._full_response = ""

    def stop(self):
        """Demande l'arrêt du streaming."""
        self._stop_requested = True

    def run(self):
        """Exécuté dans le thread secondaire."""
        self.thinking_started.emit()
        self._full_response = ""
        self._stop_requested = False

        # Construction des messages avec système prompt
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.extend(self.messages)

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
            }
        }

        try:
            with requests.post(
                f"{self.ollama_url}/api/chat",
                json=payload,
                stream=True,
                timeout=120
            ) as resp:
                if resp.status_code != 200:
                    self.error_occurred.emit(
                        f"Erreur HTTP {resp.status_code}: {resp.text[:200]}"
                    )
                    return

                for line in resp.iter_lines():
                    if self._stop_requested:
                        break
                    if not line:
                        continue
                    try:
                        data = json.loads(line.decode("utf-8"))
                        if "message" in data:
                            content = data["message"].get("content", "")
                            if content:
                                self._full_response += content
                                self.token_received.emit(content)
                        if data.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue

        except requests.exceptions.ConnectionError:
            self.error_occurred.emit(
                "❌ Impossible de se connecter à Ollama.\n"
                "Lance: ollama serve"
            )
            return
        except requests.exceptions.Timeout:
            self.error_occurred.emit("⏱️ Timeout — le modèle met trop de temps à répondre.")
            return
        except Exception as e:
            self.error_occurred.emit(f"❌ Erreur inattendue: {e}")
            return

        self.response_done.emit(self._full_response)
