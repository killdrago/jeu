# Mise à jour Admin Console IA — v2.1

## Fichiers à remplacer dans ton projet

Copie ces fichiers dans ton dossier de projet (en respectant la structure) :

```
ton-projet/
├── ui/
│   ├── main_window.py        ← REMPLACER
│   ├── chat_widget.py        ← REMPLACER
│   ├── modification_panel.py ← REMPLACER (totalement réécrit)
│   └── code_viewer.py        ← NOUVEAU FICHIER (à créer)
```

## Nouvelles fonctionnalités

### 1. Preview intégré (pas de fenêtre séparée)
- Clique sur **▶ TESTER** → l'app modifiée se lance en sous-processus
- Son output (stdout/stderr) s'affiche dans l'**onglet 🖥 Preview** du panneau droit
- Tu vois en temps réel si l'app démarre correctement

### 2. Boutons simplifiés
- **✔ ACCEPTER & APPLIQUER** → remplace les fichiers de base + recharge
- **✘ REFUSER** → rollback Git automatique + oublie la demande

### 3. Onglet "{ } Code" avec surbrillance
- Liste des fichiers modifiés (cliquables)
- Quand tu cliques sur un fichier → code complet affiché
- **Lignes modifiées = fond vert + texte gras + marqueur ▶**
- Numéros de ligne affichés à gauche

### 4. Workflow complet
```
1. Chat IA → demande "mets le fond en blanc"
2. L'IA répond (description dans le chat, code dans panneau droit)
3. Onglet "{ } Code" → sélectionne un fichier → vois les lignes modifiées
4. Onglet "Δ Diff" → vois le diff coloré complet
5. [▶ TESTER] → l'app modifiée tourne en sous-processus
6. Si OK → [✔ ACCEPTER] → les fichiers sont mis à jour
7. Si non → [✘ REFUSER] → rollback Git, rien n'a changé
```

## Pas de dépendance supplémentaire

Aucun nouveau package pip requis. Le fichier `code_viewer.py` est un simple QTextEdit.
