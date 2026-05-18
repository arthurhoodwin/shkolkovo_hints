"""
Школково — Генератор подсказок v4.0 (PyQt6)
============================================
Запуск:
    python main.py
"""
import sys
from PyQt6.QtWidgets import QApplication
from shkolkovo.app_qt import App
from shkolkovo.config import APP_QSS

def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_QSS)
    window = App()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
