import sys

from PyQt6.QtWidgets import QApplication

from shkolkovo.app_qt import App as HintsApp
from shkolkovo.config import APP_QSS
from shkolkovo.full_client_qt import FullClientApp


def _use_legacy_hints_mode(argv: list[str]) -> bool:
    return "--legacy-hints" in argv


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_QSS)
    if _use_legacy_hints_mode(sys.argv):
        window = HintsApp()
    else:
        window = FullClientApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
