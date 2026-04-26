@echo off
chcp 65001 >nul
title Admin Console — IA Locale

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║     ADMIN CONSOLE — IA LOCALE v2.0      ║
echo  ╚══════════════════════════════════════════╝
echo.

:: Vérifie Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERREUR] Python n'est pas installé ou pas dans le PATH.
    echo  Télécharge-le sur https://python.org
    pause
    exit /b 1
)

echo  [✓] Python détecté
python --version

:: Vérifie si les dépendances sont installées
python -c "import PyQt6" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [⚙] Installation des dépendances...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo  [ERREUR] Impossible d'installer les dépendances.
        pause
        exit /b 1
    )
    echo  [✓] Dépendances installées
) else (
    echo  [✓] Dépendances déjà installées
)

echo.

:: Vérifie si Ollama est lancé
echo  [⚙] Vérification Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo  [!] Ollama n'est pas lancé. L'app va démarrer quand même.
    echo  Lance Ollama dans un autre terminal: ollama serve
) else (
    echo  [✓] Ollama détecté
)

echo.
echo  [▶] Lancement de l'Admin Console...
echo.

:: Lance l'application
python main.py

if errorlevel 1 (
    echo.
    echo  [ERREUR] L'application s'est arrêtée avec une erreur.
    pause
)
