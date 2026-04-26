@echo off
:: ==================================================
::  ADMIN CONSOLE IA — Lanceur Windows
::  Double-cliquez sur ce fichier pour démarrer
:: ==================================================

title Admin Console IA

echo.
echo  ================================================
echo   ADMIN CONSOLE IA — Démarrage
echo  ================================================
echo.

:: Vérifie si Python est installé
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installé ou pas dans le PATH.
    echo Téléchargez Python sur : https://www.python.org/downloads/
    pause
    exit /b
)

:: Vérifie si Ollama est lancé
echo [1/3] Vérification d'Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [INFO] Ollama ne semble pas lancé. Tentative de démarrage...
    start "" ollama serve
    timeout /t 3 /nobreak >nul
) else (
    echo [OK] Ollama est déjà lancé.
)

:: Installe les dépendances si nécessaire
echo [2/3] Vérification des dépendances...
pip show PyQt6 >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installation des dépendances...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERREUR] L'installation a échoué. Lancez manuellement :
        echo   pip install -r requirements.txt
        pause
        exit /b
    )
)
echo [OK] Dépendances prêtes.

:: Lance l'application
echo [3/3] Démarrage de l'interface...
echo.
python main.py

if errorlevel 1 (
    echo.
    echo [ERREUR] L'application s'est fermée avec une erreur.
    pause
)
