"""
Admin Console — IA Locale avec Auto-Modification
Point d'entrée principal de l'application.
"""

import sys
import os
import json

# Assure que les imports relatifs fonctionnent
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontDatabase, QFont

from ui.main_window import MainWindow


def load_config() -> dict:
    """Charge la configuration persistante."""
    config_path = os.path.join(BASE_DIR, "config.json")
    default_config = {
        "ollama_url": "http://localhost:11434",
        "last_model": "",
        "theme": "dark",
        "font_size": 13,
        "auto_snapshot": True,
        "preview_port": 5555,
        "window_geometry": None
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_config.update(data)
        except Exception:
            pass
    return default_config


def save_config(config: dict):
    """Sauvegarde la configuration."""
    config_path = os.path.join(BASE_DIR, "config.json")
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[WARN] Impossible de sauvegarder config: {e}")


def main():
    # Active le scaling HiDPI
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    app = QApplication(sys.argv)
    app.setApplicationName("Admin Console — IA")
    app.setApplicationVersion("2.0.0")
    app.setOrganizationName("AdminIA")

    # Style global sombre
    app.setStyle("Fusion")
    apply_dark_palette(app)

    # Charge la config
    config = load_config()

    # Crée et affiche la fenêtre principale
    window = MainWindow(config, save_callback=save_config, base_dir=BASE_DIR)
    window.show()

    ret = app.exec()
    sys.exit(ret)


def apply_dark_palette(app: QApplication):
    """Applique une palette sombre globale."""
    from PyQt6.QtGui import QPalette, QColor
    from PyQt6.QtCore import Qt

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(10, 10, 10))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 255, 65))
    palette.setColor(QPalette.ColorRole.Base, QColor(15, 15, 15))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(20, 20, 20))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(0, 255, 65))
    palette.setColor(QPalette.ColorRole.Text, QColor(200, 255, 200))
    palette.setColor(QPalette.ColorRole.Button, QColor(20, 20, 20))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 255, 65))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.ColorRole.Link, QColor(0, 180, 255))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 80, 0))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 255, 65))
    app.setPalette(palette)


if __name__ == "__main__":
    main()
