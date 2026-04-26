═══════════════════════════════════════════════════════════════
  ADMIN CONSOLE — IA LOCALE v2.0
  Interface d'administration avec auto-modification par l'IA
═══════════════════════════════════════════════════════════════

STRUCTURE DES FICHIERS
──────────────────────
admin-console/
├── main.py                 ← Point d'entrée principal
├── lancer.bat              ← Double-clic pour lancer (Windows)
├── requirements.txt        ← Dépendances Python
├── config.json             ← Créé automatiquement au 1er lancement
│
├── core/
│   ├── model_detector.py   ← Détection auto des modèles Ollama
│   ├── ollama_worker.py    ← Streaming IA (QThread)
│   ├── code_modifier.py    ← Extraction + validation du code IA
│   ├── git_snapshot.py     ← Snapshots Git automatiques
│   └── app_reloader.py     ← Lancement preview + rechargement
│
├── ui/
│   ├── main_window.py      ← Fenêtre principale
│   ├── model_bar.py        ← Barre de sélection modèle
│   ├── chat_widget.py      ← Zone de chat streaming
│   ├── modification_panel.py ← Panel validation modifications
│   ├── file_browser.py     ← Navigateur de fichiers
│   ├── snapshot_panel.py   ← Historique Git / rollback
│   ├── diff_viewer.py      ← Visualiseur de diff coloré
│   └── styles.py           ← Thème terminal sombre centralisé
│
└── model/
    └── Modelfile.exemple   ← Exemple pour .gguf local


INSTALLATION & LANCEMENT
─────────────────────────
1. Ouvre un terminal dans le dossier admin-console/

2. Installe les dépendances:
   pip install -r requirements.txt

3. Lance Ollama (dans un autre terminal):
   ollama serve

4. Charge un modèle (si pas encore fait):
   ollama pull llama3.2
   # ou pour un .gguf local:
   ollama create mon-modele -f ./model/Modelfile

5. Lance l'app:
   python main.py
   # ou double-clic sur lancer.bat (Windows)


COMMENT UTILISER L'AUTO-MODIFICATION
──────────────────────────────────────

WORKFLOW COMPLET:
  1. Chat avec l'IA → demande une modification de code
  2. L'IA répond avec le code modifié (format ## FILE:)
  3. Le panneau droit s'active avec le diff coloré
  4. Clique [▶ PREVIEW] → une 2e fenêtre de l'app modifiée s'ouvre
  5. Tu testes la version modifiée
  6. Si OK → clique [✔ VALIDER & APPLIQUER]
     → Les fichiers sont modifiés + l'app se relance
  7. Si non → clique [✘ REFUSER]
     → Rollback Git automatique, rien n'a changé

EXEMPLES DE DEMANDES À L'IA:
  "Modifie ui/chat_widget.py pour que les messages utilisateur
   s'affichent en orange au lieu de bleu"

  "Ajoute un bouton 'Effacer l'historique' dans la barre de modèle"

  "Modifie core/ollama_worker.py pour ajouter un timeout
   configurable dans la config.json"

COMMANDES SPÉCIALES DANS LE CHAT:
  /fichiers              → Liste tous les fichiers de l'app
  /modifier fichier.py   → Charge un fichier en contexte pour l'IA
  /snapshot              → Crée un snapshot Git maintenant
  /historique            → Ouvre l'onglet des snapshots
  /aide                  → Affiche l'aide

ONGLET FICHIERS:
  - Navigue dans les fichiers de l'app
  - Clique sur un fichier → vois son code
  - Bouton [🤖 Demander à l'IA de modifier ce fichier]
    → Charge le fichier en contexte + ouvre le chat


FORMAT ATTENDU DE LA RÉPONSE IA
─────────────────────────────────
Pour que l'auto-modification fonctionne, l'IA doit répondre
avec ce format (le prompt système l'y encourage automatiquement):

  ## FILE: ui/chat_widget.py
  ```python
  # contenu complet du fichier modifié
  ```

  ## FILE: core/ollama_worker.py
  ```python
  # autre fichier si modification multiple
  ```

Si l'IA ne respecte pas ce format, dis-lui:
  "Utilise le format ## FILE: pour ta réponse"


SÉCURITÉ & SNAPSHOTS GIT
──────────────────────────
- Avant toute modification, un snapshot Git est créé automatiquement
- Si tu refuses → rollback automatique = 0 risque de casser l'app
- Si tu valides → snapshot post-modification créé aussi
- Onglet [📸 Snapshots] pour voir l'historique et faire des rollbacks manuels
- Git est initialisé automatiquement dans le dossier si absent

DOSSIER _preview/
  - Créé temporairement quand tu cliques [▶ PREVIEW]
  - Supprimé si tu refuses
  - JAMAIS modifié si tu refuses
  - L'app de base reste intacte jusqu'à ta validation


DÉPANNAGE
──────────
Problème: "Ollama non détecté"
  → Lance: ollama serve (dans un autre terminal)

Problème: "Aucun modèle trouvé"
  → Lance: ollama pull llama3.2
  → Ou crée ton modèle: ollama create mon-model -f ./model/Modelfile

Problème: L'IA ne répond pas
  → Vérifie que le modèle est bien chargé: ollama list
  → Le modèle est peut-être trop gros pour ton RAM

Problème: L'IA ne génère pas de code modifiable
  → Dis-lui explicitement: "Modifie le fichier X.py et utilise
    le format ## FILE: pour ta réponse"

Problème: Git non disponible
  → Les snapshots ne fonctionneront pas
  → Installe Git: https://git-scm.com/
  → L'app fonctionne quand même, juste sans backup automatique


CONFIGURATION (config.json)
────────────────────────────
{
  "ollama_url": "http://localhost:11434",  ← URL de ton Ollama
  "last_model": "llama3.2",               ← Dernier modèle utilisé
  "theme": "dark",                         ← Thème (dark uniquement pour l'instant)
  "font_size": 13,                         ← Taille de police
  "auto_snapshot": true,                   ← Snapshot auto avant modification
  "preview_port": 5555                     ← Port pour le preview (réservé)
}


STACK TECHNIQUE
───────────────
  Python 3.10+    → Langage principal
  PyQt6           → Interface graphique (GPU, multi-thread)
  Ollama          → Serveur LLM local (gratuit, offline)
  Git (subprocess)→ Snapshots et rollback
  ast.parse()     → Validation syntaxique du code Python
  QThread         → L'IA ne JAMAIS sur le thread UI = pas de freeze

═══════════════════════════════════════════════════════════════
