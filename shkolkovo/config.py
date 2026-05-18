from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://1.shkolkovo.online/api"
MAX_HISTORY = 30

# ── Palette ───────────────────────────────────────────────
BG       = "#0f1115"
SURFACE  = "#171a21"
CARD     = "#1f2430"
BORDER   = "#31394a"
ACCENT   = "#2b84ff"
ACCENT2  = "#0ea5a3"
SUCCESS  = "#22c55e"
DANGER   = "#ef4444"
WARNING  = "#f59e0b"
TEXT     = "#e7edf7"
MUTED    = "#8c97ac"

HINT_ACCENTS = ["#3b82f6","#10b981","#f59e0b","#8b5cf6","#ec4899","#06b6d4"]

# ── Global QSS ────────────────────────────────────────────
APP_QSS = f"""
* {{ outline: none; }}
QMainWindow, QWidget {{ background: {BG}; color: {TEXT};
    font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 13px; }}
QSplitter::handle {{ background: {BORDER}; }}
QSplitter::handle:horizontal {{ width: 2px; }}
QSplitter::handle:vertical   {{ height: 2px; }}

QLineEdit, QTextEdit, QPlainTextEdit {{
    background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 6px; padding: 4px 10px; selection-background-color: {ACCENT};
}}
QLineEdit:focus, QTextEdit:focus {{ border-color: {ACCENT}; background: {CARD}; }}

QComboBox {{
    background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 6px; padding: 4px 10px;
}}
QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: none; }}
QComboBox QAbstractItemView {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 6px;
    color: {TEXT}; padding: 2px; outline: none;
}}
QComboBox QAbstractItemView::item {{
    color: {TEXT}; padding: 5px 10px; border-radius: 4px; min-height: 22px;
}}
QComboBox QAbstractItemView::item:hover {{
    background: {ACCENT}; color: white;
}}
QComboBox QAbstractItemView::item:selected {{
    background: {ACCENT}; color: white;
}}

QPushButton {{
    background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 6px; padding: 5px 14px; font-weight: 600;
}}
QPushButton:hover  {{ background: {CARD}; border-color: {ACCENT}; color: white; }}
QPushButton:pressed{{ background: {ACCENT}; color: white; border-color: {ACCENT}; }}
QPushButton:disabled{{ color: {MUTED}; border-color: {BORDER}; background: {BG}; }}

QPushButton[accent="true"] {{ background: {ACCENT}; color: white; border: none; }}
QPushButton[accent="true"]:hover  {{ background: #1a5ce8; }}
QPushButton[accent="true"]:pressed{{ background: #0e46cc; }}
QPushButton[accent="true"]:disabled{{ background: #1a2a4a; color: #4a6080; }}

QPushButton[success="true"] {{ background: {SUCCESS}; color: white; border: none; font-weight: 700; }}
QPushButton[success="true"]:hover  {{ background: #16a34a; }}

QPushButton[danger="true"] {{ background: {DANGER}; color: white; border: none; }}
QPushButton[danger="true"]:hover  {{ background: #dc2626; }}

QPushButton[accent2="true"] {{ background: {ACCENT2}; color: white; border: none; }}
QPushButton[accent2="true"]:hover  {{ background: #5b2ecc; }}

QScrollBar:vertical {{
    background: transparent; width: 7px; border-radius: 3px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; border-radius: 3px; min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: {MUTED}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

QScrollBar:horizontal {{
    background: transparent; height: 7px; border-radius: 3px; margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER}; border-radius: 3px; min-width: 28px;
}}
QScrollBar::handle:horizontal:hover {{ background: {MUTED}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}

QLabel {{ color: {TEXT}; background: transparent; }}
QLabel[muted="true"] {{ color: {MUTED}; font-size: 11px; }}

QMessageBox {{ background: {CARD}; }}
QMessageBox QLabel {{ color: {TEXT}; }}
QMessageBox QPushButton {{ min-width: 80px; }}

QTreeWidget, QListWidget {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px;
    alternate-background-color: {CARD}; outline: none;
}}
QTreeWidget::item {{ padding: 3px 0; }}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background: {ACCENT}; color: white; border-radius: 3px;
}}
QHeaderView::section {{
    background: {CARD}; color: {MUTED}; border: none;
    border-bottom: 1px solid {BORDER}; padding: 5px 8px;
    font-size: 11px; font-weight: 700;
}}

QProgressBar {{ background: {SURFACE}; border: none; border-radius: 3px; height: 4px; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}

QSlider::groove:horizontal {{ background: {BORDER}; height: 4px; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: white; width: 14px; height: 14px; border-radius: 7px;
    margin: -5px 0; border: 2px solid {ACCENT};
}}
QSlider::handle:horizontal:hover {{ background: {ACCENT}; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}

QCheckBox {{ spacing: 7px; color: {TEXT}; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border: 1.5px solid {BORDER};
    border-radius: 4px; background: {SURFACE};
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}

QFrame[card="true"] {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 8px;
}}

QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 10px;
    padding: 10px 10px 8px 10px;
    background: {CARD};
    font-weight: 700;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px 0 6px;
    color: {TEXT};
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 8px;
    background: {CARD};
}}
QTabBar::tab {{
    background: {SURFACE};
    color: {MUTED};
    border: 1px solid {BORDER};
    border-bottom: none;
    min-width: 104px;
    min-height: 32px;
    padding: 6px 12px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: 700;
}}
QTabBar::tab:selected {{
    color: white;
    background: {ACCENT};
    border-color: {ACCENT};
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT};
    border-color: {ACCENT};
}}

QTableWidget {{
    background: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER};
    selection-background-color: #21477c;
    selection-color: white;
}}
QTableWidget::item {{
    padding: 4px;
}}
QTableCornerButton::section {{
    background: {CARD};
    border: 1px solid {BORDER};
}}

QStatusBar {{ background: {SURFACE}; border-top: 1px solid {BORDER}; font-size: 12px; }}
QStatusBar QLabel {{ color: {TEXT}; padding: 3px 8px; }}

QToolTip {{
    background: {CARD}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 4px; padding: 4px 8px; font-size: 12px;
}}
"""
