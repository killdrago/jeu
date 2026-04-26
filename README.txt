==================================================
  ADMIN CONSOLE IA — Guide d'installation
==================================================

STRUCTURE DES FICHIERS
──────────────────────
  admin-console/
  ├── main.py              ← Point d'entrée (lancer ce fichier)
  ├── lancer.bat           ← Double-clic pour démarrer sous Windows
  ├── requirements.txt     ← Dépendances Python
  ├── README.txt           ← Ce fichier
  │
  ├── ui/                  ← Interface graphique
  │   ├── __init__.py
  │   ├── main_window.py   ← Fenêtre principale
  │   ├── model_bar.py     ← Barre de statut modèle
  │   └── chat_widget.py   ← Zone de chat
  │
  ├── core/                ← Logique métier
  │   ├── __init__.py
  │   ├── model_detector.py ← Détection auto du modèle
  │   └── ollama_worker.py  ← Streaming IA (QThread)
  │
  └── model/               ← Placez vos fichiers modèle ici
      └── Modelfile.exemple ← Exemple de Modelfile


PRÉREQUIS
──────────────────────

1. Python 3.10 ou plus récent
   → https://www.python.org/downloads/
   → Cochez "Add Python to PATH" lors de l'installation

2. Ollama (moteur IA local, GRATUIT)
   → https://ollama.com/download
   → Installez-le, il tourne en arrière-plan


INSTALLATION
──────────────────────

Option A — Double-clic (Windows) :
   → Double-cliquez sur lancer.bat
   → Tout est automatique

Option B — Terminal manuel :
   pip install -r requirements.txt
   ollama serve
   python main.py


AJOUTER VOTRE MODÈLE
──────────────────────

Méthode 1 — Télécharger un modèle depuis Ollama :
   ollama pull llama3.2          (3B, ~2 GB, rapide)
   ollama pull mistral           (7B, ~4 GB, bon équilibre)
   ollama pull deepseek-r1:7b    (7B, raisonnement)
   ollama pull phi4-mini         (3.8B, très rapide)

Méthode 2 — Utiliser votre propre fichier .gguf :
   1. Placez votre fichier .gguf dans le dossier model/
   2. Copiez model/Modelfile.exemple → model/Modelfile
   3. Modifiez la ligne FROM dans Modelfile
   4. Dans un terminal :
        ollama create mon-model -f ./model/Modelfile
   5. Cliquez [AUTO] dans l'interface

L'interface détecte automatiquement le modèle au démarrage.
Si vous changez de modèle, cliquez juste sur [AUTO].


UTILISATION
──────────────────────

[AUTO]   → Détecte le modèle automatiquement via Ollama
[MANUEL] → Entrez le nom du modèle à la main
           (utile si plusieurs modèles sont installés)

Entrée          → Envoyer le message
Shift + Entrée  → Saut de ligne
↑ / ↓          → Naviguer dans l'historique des commandes
■ STOP          → Interrompre la génération en cours


POURQUOI PAS TKINTER ?
──────────────────────
L'ancienne interface Tkinter gelait car :
  - Tkinter est mono-thread (tout sur le même thread)
  - L'IA qui "réfléchit" + l'UI = freeze garanti

Cette interface utilise PyQt6 + QThread :
  - L'IA tourne dans un thread SÉPARÉ
  - L'UI reste toujours réactive
  - Le streaming est fluide token par token


PROBLÈMES COURANTS
──────────────────────

"Impossible de contacter Ollama"
  → Lancez : ollama serve
  → Vérifiez que rien ne bloque le port 11434

"Aucun modèle installé"
  → Lancez : ollama pull llama3.2
  → Ou importez votre .gguf (voir ci-dessus)

"Module PyQt6 introuvable"
  → Lancez : pip install PyQt6

L'interface ne démarre pas :
  → Lancez python main.py dans un terminal
  → Lisez le message d'erreur


==================================================
