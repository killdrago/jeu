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

    echo  [ERREUR] Python n'est pas installe ou pas dans le PATH.

    echo  Telechargez-le sur https://python.org

    pause

    exit /b 1

)

echo  [OK] Python detecte

python --version

echo.

:: ─────────────────────────────────────────────

:: NETTOYAGE PyQt5 si present (cause le crash preview)

:: ─────────────────────────────────────────────

python -c "import PyQt5" >nul 2>&1

if not errorlevel 1 (

    echo  [!] PyQt5 detecte — desinstallation en cours...

    pip uninstall PyQt5 PyQt5-Qt5 PyQt5-sip -y >nul 2>&1

    echo  [OK] PyQt5 desinstalle

)

:: Verifie/installe PyQt6

python -c "import PyQt6" >nul 2>&1

if errorlevel 1 (

    echo  [!] PyQt6 non trouve — installation...

    pip install -r requirements.txt

    if errorlevel 1 (

        echo  [ERREUR] Impossible d'installer les dependances.

        pause

        exit /b 1

    )

    echo  [OK] Dependances installees

) else (

    echo  [OK] PyQt6 deja installe

    :: Verifie qu'il n'y a pas de PyQt6-Qt6 conflictuel

    pip install --upgrade PyQt6 >nul 2>&1

)

:: Vérifie Ollama

echo  [!] Verification Ollama...

curl -s http://localhost:11434/api/tags >nul 2>&1

if errorlevel 1 (

    echo  [!] Ollama non lance. L'app demarre quand meme.

    echo  Lancez Ollama dans un autre terminal: ollama serve

) else (

    echo  [OK] Ollama detecte

)

echo.

echo  [>] Lancement Admin Console...

echo.

python main.py

if errorlevel 1 (

    echo.

    echo  [ERREUR] L'application s'est arretee avec une erreur.

    pause

)