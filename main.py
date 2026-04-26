"""
=======================================================
  ADMIN CONSOLE IA — Point d'entrée principal
=======================================================
  Lance ce fichier avec : python main.py
  Prérequis : pip install -r requirements.txt
              Ollama lancé : ollama serve
=======================================================
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Admin Console IA")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
