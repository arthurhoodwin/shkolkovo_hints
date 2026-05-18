"""app_qt.py — главное окно приложения на PyQt6."""
from __future__ import annotations

import base64
import datetime
import json
import os
import re
import webbrowser
from concurrent.futures import ThreadPoolExecutor

import requests
from PyQt6.QtCore import (Qt, QRunnable, QThreadPool, pyqtSignal,
                           QObject, pyqtSlot, QTimer)
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QPushButton, QLabel, QLineEdit, QComboBox, QTextEdit,
    QSlider, QFrame, QCheckBox, QProgressBar, QScrollArea,
    QStatusBar, QMessageBox, QFileDialog, QApplication,
    QStackedWidget,
)
from PyQt6.QtGui import QFont, QKeySequence, QShortcut

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_OK = True
except ImportError:
    WEBENGINE_OK = False

from .api import (
    _apply_ssl, _friendly_request_error,
    extract_tex_body, fetch_latex_session, fetch_question,
    fetch_questions_without_hints, filter_question_ids_without_hints,
    save_hints_to_platform, set_proxy,
)
from .config import (
    BASE_URL, MAX_HISTORY, ACCENT, ACCENT2, SUCCESS, DANGER,
    WARNING, TEXT, MUTED, CARD, BORDER, SURFACE, BG, HINT_ACCENTS,
)
from .dialogs_qt import (
    SettingsDialog, ThemeQueueDialog, LogDialog,
    HintPreviewDialog, ask_text,
)
from .generation import MODELS, fetch_free_models_from_groq, generate_hints_groq
from .log_store import CsvProcessLogStore
from .widgets_qt import HintsEditor

VERSION = "v4.0-qt"
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".shkolkovo_v4.json")


# ── Worker helpers ────────────────────────────────────────────────────────────

class _Signals(QObject):
    result = pyqtSignal(object)
    error  = pyqtSignal(str)

class _Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.signals = _Signals()

    @pyqtSlot()
    def run(self):
        try:
            self.signals.result.emit(self.fn(*self.args, **self.kwargs))
        except Exception as exc:
            self.signals.error.emit(str(exc))


def _run(fn, *a, on_result=None, on_error=None, **kw):
    w = _Worker(fn, *a, **kw)
    if on_result:
        w.signals.result.connect(on_result)
    if on_error:
        w.signals.error.connect(on_error)
    QThreadPool.globalInstance().start(w)


# ── Small UI helpers ──────────────────────────────────────────────────────────

def _btn(text: str, prop: str | None = None,
         width: int | None = None, height: int | None = None,
         tooltip: str = "") -> QPushButton:
    b = QPushButton(text)
    if prop:
        b.setProperty(prop, "true")
    if width:
        b.setFixedWidth(width)
    if height:
        b.setFixedHeight(height)
    if tooltip:
        b.setToolTip(tooltip)
    return b


def _label(text: str, bold: bool = False, muted: bool = False,
           size: int | None = None) -> QLabel:
    lbl = QLabel(text)
    if bold or size:
        f = lbl.font()
        if bold:  f.setBold(True)
        if size:  f.setPointSize(size)
        lbl.setFont(f)
    if muted:
        lbl.setStyleSheet(f"color:{MUTED}; font-size:11px;")
    return lbl


def _separator(vertical: bool = False) -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine if vertical
                    else QFrame.Shape.HLine)
    f.setStyleSheet(f"color:{BORDER};")
    return f


def _card_frame() -> QFrame:
    f = QFrame()
    f.setProperty("card", "true")
    return f


# ── Main window ───────────────────────────────────────────────────────────────

class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Школково — Генератор подсказок {VERSION}")
        self.resize(1440, 880)
        self.setMinimumSize(1000, 660)

        # State
        self._question_data: dict | None = None
        self._question_html = ""
        self._solution_html = ""
        self._question_tex  = ""
        self._solution_tex  = ""
        self._id_history: list[str] = []
        self._settings = {"proxy": "", "verify_ssl": True}
        self._gen_count  = 0
        self._batch_queue: list[str] = []
        self._batch_total = 0
        self._batch_running = False
        self._task_start_ts: float = 0.0
        self._task_times: list[float] = []
        self._tasks_done = 0
        self._ref_question = ""
        self._ref_hints: list = []
        self._prompt_profiles: dict[str, str] = {}
        self._process_log: list[dict] = []
        self._log_store = CsvProcessLogStore()

        self._build_ui()
        self._bind_shortcuts()
        self._load_log()
        self._load_settings()

    # ═════════════════════════════════════════════════════════════════════════
    #  UI BUILD
    # ═════════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        vlay = QVBoxLayout(root)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)

        vlay.addWidget(self._mk_topbar())
        vlay.addWidget(self._mk_searchbar())
        vlay.addWidget(self._mk_main(), 1)
        self._mk_statusbar()

    # ── Topbar ────────────────────────────────────────────────────────────────

    def _mk_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(f"background:{CARD}; border-bottom:1px solid {BORDER};")
        bar.setFixedHeight(52)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Logo
        logo = QLabel("  🎓  Школково  ")
        logo.setFixedWidth(130)
        logo.setFixedHeight(52)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(
            f"background:{ACCENT}; color:white; font-weight:700; font-size:13px;")
        lay.addWidget(logo)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color:{BORDER};")
        lay.addWidget(sep)

        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        ilay = QHBoxLayout(inner)
        ilay.setContentsMargins(12, 0, 12, 0)
        ilay.setSpacing(10)

        # JWT
        ilay.addWidget(_label("JWT:", muted=True))
        self.token_entry = QLineEdit()
        self.token_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_entry.setPlaceholderText("eyJhbGciOiJ…")
        self.token_entry.setFixedWidth(190)
        self.token_entry.setFixedHeight(32)
        ilay.addWidget(self.token_entry)
        self._jwt_label = _label("")
        self._jwt_label.setFixedWidth(48)
        ilay.addWidget(self._jwt_label)
        self.token_entry.editingFinished.connect(self._update_jwt_label)
        QTimer.singleShot(500, self._update_jwt_label)

        ilay.addWidget(_separator(vertical=True))

        # API Key
        ilay.addWidget(_label("Groq Key:", muted=True))
        self.api_key_entry = QLineEdit()
        self.api_key_entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_entry.setPlaceholderText("gsk-…")
        self.api_key_entry.setFixedWidth(190)
        self.api_key_entry.setFixedHeight(32)
        ilay.addWidget(self.api_key_entry)

        ilay.addWidget(_separator(vertical=True))

        # Model
        ilay.addWidget(_label("Модель:", muted=True))
        self.model_combo = QComboBox()
        self.model_combo.addItems(MODELS)
        self.model_combo.setFixedWidth(190)
        self.model_combo.setFixedHeight(32)
        ilay.addWidget(self.model_combo)

        refresh = _btn("↻", tooltip="Обновить список моделей")
        refresh.setFixedSize(28, 28)
        refresh.clicked.connect(self._fetch_models)
        ilay.addWidget(refresh)

        ilay.addStretch()

        ilay.addWidget(_separator(vertical=True))

        # Named buttons
        settings_btn = _btn("⚙ Настройки", tooltip="Открыть настройки подключения")
        settings_btn.setFixedHeight(32)
        settings_btn.clicked.connect(self._open_settings)
        ilay.addWidget(settings_btn)

        save_btn = _btn("💾 Сохранить", tooltip="Сохранить настройки")
        save_btn.setFixedHeight(32)
        save_btn.clicked.connect(self._save_settings)
        ilay.addWidget(save_btn)

        lay.addWidget(inner, 1)
        return bar

    # ── Searchbar ─────────────────────────────────────────────────────────────

    def _mk_searchbar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(f"background:{SURFACE}; border-bottom:2px solid {ACCENT};")
        vlay = QVBoxLayout(bar)
        vlay.setContentsMargins(14, 8, 14, 8)
        vlay.setSpacing(6)

        # Row 1: single task
        r1 = QHBoxLayout()
        r1.setSpacing(8)
        r1.addWidget(_label("ID задачи", bold=True))

        self.question_id_entry = QLineEdit()
        self.question_id_entry.setPlaceholderText("101599")
        self.question_id_entry.setFixedWidth(110)
        self.question_id_entry.setFixedHeight(34)
        self.question_id_entry.returnPressed.connect(self._fetch_question)
        r1.addWidget(self.question_id_entry)

        self.history_combo = QComboBox()
        self.history_combo.setFixedWidth(130)
        self.history_combo.setFixedHeight(34)
        self.history_combo.addItem("(история)")
        self.history_combo.currentTextChanged.connect(self._on_history_select)
        r1.addWidget(self.history_combo)

        self.fetch_btn = _btn("📥 Загрузить", "accent", height=34)
        self.fetch_btn.clicked.connect(self._fetch_question)
        r1.addWidget(self.fetch_btn)

        browser_btn = _btn("↗ В браузер", height=34, tooltip="Открыть задачу в браузере")
        browser_btn.clicked.connect(self._open_in_browser)
        r1.addWidget(browser_btn)

        self.question_title_label = _label("", bold=True)
        self.question_title_label.setStyleSheet(f"color:{ACCENT}; font-size:13px;")
        self.question_title_label.hide()
        r1.addWidget(self.question_title_label)

        self.question_badge = _label("")
        self.question_badge.setStyleSheet(
            f"background:{CARD}; color:{MUTED}; border-radius:4px;"
            f" padding:2px 8px; font-size:10px;")
        self.question_badge.hide()
        r1.addWidget(self.question_badge)
        r1.addStretch()
        vlay.addLayout(r1)

        # Row 2: batch
        r2 = QHBoxLayout()
        r2.setSpacing(8)
        r2.addWidget(_label("Пакет", muted=True))

        self.batch_entry = QLineEdit()
        self.batch_entry.setPlaceholderText("101599, 101600   или   101599–101610")
        self.batch_entry.setFixedHeight(28)
        r2.addWidget(self.batch_entry, 1)

        self._batch_btn = _btn("▶ Запустить пакет", "accent2", height=28)
        self._batch_btn.clicked.connect(self._start_batch)
        r2.addWidget(self._batch_btn)

        theme_btn = _btn("📂 Из темы", height=28, tooltip="Загрузить задачи без подсказок по ID темы")
        theme_btn.clicked.connect(self._open_theme_dialog)
        r2.addWidget(theme_btn)

        skip_btn = _btn("⏭ Скип", height=28, tooltip="Пропустить текущую задачу в пакете")
        skip_btn.clicked.connect(self._batch_skip)
        r2.addWidget(skip_btn)
        self._skip_btn = skip_btn

        self._stats_label = _label("", muted=True)
        r2.addWidget(self._stats_label)

        log_btn = _btn("📋 Лог", height=28)
        log_btn.clicked.connect(self._show_log)
        r2.addWidget(log_btn)

        self._batch_status = _label("Пакет ждёт запуска", muted=True)
        r2.addWidget(self._batch_status)

        vlay.addLayout(r2)

        # Batch progress strip — thin bar under the two rows
        from PyQt6.QtWidgets import QProgressBar as _QPB
        self._batch_progress_bar = _QPB()
        self._batch_progress_bar.setFixedHeight(3)
        self._batch_progress_bar.setTextVisible(False)
        self._batch_progress_bar.setRange(0, 100)
        self._batch_progress_bar.setValue(0)
        self._batch_progress_bar.setVisible(False)
        self._batch_progress_bar.setStyleSheet(
            f"QProgressBar{{background:transparent;border:none;border-radius:0;}}"
            f"QProgressBar::chunk{{background:{ACCENT2};border-radius:0;}}")
        vlay.addWidget(self._batch_progress_bar)
        return bar

    # ── Main 3-column ─────────────────────────────────────────────────────────

    def _mk_main(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(3)

        splitter.addWidget(self._mk_left())
        splitter.addWidget(self._mk_mid())
        splitter.addWidget(self._mk_right())
        splitter.setSizes([520, 400, 520])
        return splitter

    # ── Left: question + solution ─────────────────────────────────────────────

    def _mk_left(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 4, 8)
        lay.setSpacing(6)

        # Header
        hdr = QHBoxLayout()
        hdr.addWidget(_label("Задача и решение", bold=True, size=13))
        hdr.addStretch()
        if WEBENGINE_OK:
            self._render_btn = _btn("🖥 Рендер", height=28,
                                     tooltip="Показать отрендеренный HTML")
            self._render_btn.clicked.connect(self._toggle_render)
            hdr.addWidget(self._render_btn)
        lay.addLayout(hdr)

        # Tab buttons
        tab_row = QHBoxLayout()
        self._tab_q_btn = _btn("📄 Условие", "accent", height=30)
        self._tab_s_btn = _btn("🔑 Решение", height=30)
        self._tab_q_btn.clicked.connect(lambda: self._switch_tab("q"))
        self._tab_s_btn.clicked.connect(lambda: self._switch_tab("s"))
        tab_row.addWidget(self._tab_q_btn)
        tab_row.addWidget(self._tab_s_btn)
        tab_row.addStretch()
        lay.addLayout(tab_row)

        # QStackedWidget — один виджет поверх другого, без flash
        self._left_stack = QStackedWidget()

        # Page 0: question tex
        self.question_tex_view = QTextEdit()
        self.question_tex_view.setReadOnly(True)
        self.question_tex_view.setPlaceholderText("Условие задачи (LaTeX)…")
        self.question_tex_view.setStyleSheet(
            f"font-family: 'Consolas', monospace; font-size: 12px;")

        # Page 1: solution tex
        self.solution_tex_view = QTextEdit()
        self.solution_tex_view.setReadOnly(True)
        self.solution_tex_view.setPlaceholderText("Решение (LaTeX)…")
        self.solution_tex_view.setStyleSheet(
            f"font-family: 'Consolas', monospace; font-size: 12px;")

        self._left_stack.addWidget(self.question_tex_view)   # idx 0
        self._left_stack.addWidget(self.solution_tex_view)   # idx 1

        if WEBENGINE_OK:
            # Page 2: question html
            self.question_web = QWebEngineView()
            self.question_web.setPage(self.question_web.page())
            # Page 3: solution html
            self.solution_web = QWebEngineView()
            self.solution_web.setPage(self.solution_web.page())
            self._left_stack.addWidget(self.question_web)    # idx 2
            self._left_stack.addWidget(self.solution_web)    # idx 3

        self._left_stack.setCurrentIndex(0)
        lay.addWidget(self._left_stack, 1)

        self._current_tab  = "q"    # "q" | "s"
        self._render_mode  = "tex"  # "tex" | "html"
        return w

    # ── Mid: prompt + settings ────────────────────────────────────────────────

    def _mk_mid(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 8, 4, 8)
        lay.setSpacing(6)

        lay.addWidget(_label("Стратегия генерации", bold=True, size=13))

        # Prompt toolbar
        ptb = QHBoxLayout()
        self._char_label = _label("0 симв.", muted=True)
        ptb.addWidget(self._char_label)
        ptb.addStretch()
        for txt, fn in [("↺ Сброс", self._reset_prompt),
                        ("📂 Открыть", self._load_prompt_file),
                        ("💾 Сохр.", self._save_prompt_file)]:
            b = _btn(txt, height=26)
            b.clicked.connect(fn)
            ptb.addWidget(b)
        lay.addLayout(ptb)

        # Profile row
        prf = QHBoxLayout()
        prf.addWidget(_label("Профиль:", muted=True))
        self._profile_combo = QComboBox()
        self._profile_combo.addItem("(выбрать профиль)")
        self._profile_combo.setFixedHeight(28)
        self._profile_combo.currentTextChanged.connect(self._on_profile_select)
        prf.addWidget(self._profile_combo, 1)
        save_p = _btn("＋ Сохранить", height=28)
        save_p.clicked.connect(self._save_profile)
        del_p = _btn("✕ Удалить", "danger", height=28)
        del_p.clicked.connect(self._delete_profile)
        prf.addWidget(save_p)
        prf.addWidget(del_p)
        lay.addLayout(prf)

        # Prompt textarea
        self.prompt_text = QTextEdit()
        self.prompt_text.setPlaceholderText("Системный промпт для LLM…")
        self.prompt_text.setText(self._default_prompt())
        self.prompt_text.textChanged.connect(self._update_char_count)
        lay.addWidget(self.prompt_text, 1)

        # Reference task — always visible compact row
        ref_card = _card_frame()
        ref_lay = QVBoxLayout(ref_card)
        ref_lay.setContentsMargins(10, 8, 10, 8)
        ref_lay.setSpacing(4)

        ref_hdr = QHBoxLayout()
        ref_hdr.addWidget(_label("📎 Эталонная задача", bold=True))
        self._ref_status = _label("не загружена", muted=True)
        ref_hdr.addWidget(self._ref_status)
        ref_hdr.addStretch()
        ref_lay.addLayout(ref_hdr)

        ref_row = QHBoxLayout()
        ref_row.setSpacing(6)
        self._ref_id_edit = QLineEdit()
        self._ref_id_edit.setPlaceholderText("ID эталонной задачи")
        self._ref_id_edit.setFixedHeight(28)
        self._ref_id_edit.returnPressed.connect(self._load_reference)
        ref_row.addWidget(self._ref_id_edit, 1)
        load_ref = _btn("Загрузить", "accent", height=28)
        load_ref.clicked.connect(self._load_reference)
        ref_row.addWidget(load_ref)
        clr_ref = _btn("Очистить", height=28)
        clr_ref.clicked.connect(self._clear_reference)
        ref_row.addWidget(clr_ref)
        ref_lay.addLayout(ref_row)
        lay.addWidget(ref_card)

        # Temperature
        tmp_row = QHBoxLayout()
        tmp_row.addWidget(_label("Температура:", muted=True))
        self._temp_slider = QSlider(Qt.Orientation.Horizontal)
        self._temp_slider.setRange(0, 200)
        self._temp_slider.setValue(70)
        self._temp_slider.setFixedHeight(20)
        self._temp_slider.valueChanged.connect(self._on_temp_change)
        tmp_row.addWidget(self._temp_slider, 1)
        self._temp_label = _label("0.70", muted=True)
        self._temp_label.setFixedWidth(36)
        tmp_row.addWidget(self._temp_label)
        lay.addLayout(tmp_row)

        # Generate button
        self.generate_btn = _btn("✨ Сгенерировать подсказки", "accent", height=48)
        f = self.generate_btn.font()
        f.setPointSize(14); f.setBold(True)
        self.generate_btn.setFont(f)
        self.generate_btn.clicked.connect(self._generate_hints)
        lay.addWidget(self.generate_btn)

        return w

    # ── Right: hints editor ───────────────────────────────────────────────────

    def _mk_right(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(4, 8, 8, 8)
        lay.setSpacing(6)

        hdr = QHBoxLayout()
        hdr.addWidget(_label("Подсказки", bold=True, size=13))
        self._hint_count_label = _label("0", muted=True)
        hdr.addWidget(self._hint_count_label)
        hdr.addStretch()
        lay.addLayout(hdr)

        self.hints_editor = HintsEditor()
        self.hints_editor.changed.connect(self._update_hint_count)
        self.hints_editor.regen_one.connect(self._regen_single_hint)
        lay.addWidget(self.hints_editor, 1)

        # Action buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self.retry_btn = _btn("🔄 Переделать", height=34)
        self.retry_btn.clicked.connect(self._generate_hints)
        btn_row.addWidget(self.retry_btn, 1)

        clr = _btn("🗑 Очистить", height=34)
        clr.clicked.connect(lambda: (self.hints_editor.clear(),
                                     self._update_hint_count()))
        btn_row.addWidget(clr, 1)

        cp_json = _btn("📋 JSON", height=34)
        cp_json.clicked.connect(self._copy_json)
        btn_row.addWidget(cp_json, 1)

        self.approve_btn = _btn("✅ Отправить", "success", height=34)
        f = self.approve_btn.font(); f.setBold(True); self.approve_btn.setFont(f)
        self.approve_btn.clicked.connect(self._approve_hints)
        btn_row.addWidget(self.approve_btn, 1)
        lay.addLayout(btn_row)

        # Aux row
        aux = QHBoxLayout()
        preview = _btn("👁 Просмотр", height=30)
        preview.clicked.connect(self._show_preview)
        aux.addWidget(preview)
        add_card = _btn("＋ Добавить карточку", height=30)
        add_card.clicked.connect(lambda: (self.hints_editor.add_empty_hint(),
                                           self._update_hint_count()))
        aux.addStretch()
        aux.addWidget(add_card)
        lay.addLayout(aux)

        return w

    # ── Status bar ────────────────────────────────────────────────────────────

    def _mk_statusbar(self):
        sb = self.statusBar()
        sb.setStyleSheet(f"background:{SURFACE}; border-top:1px solid {BORDER};")

        self._status_label = QLabel("● Готово к работе")
        self._status_label.setStyleSheet(f"color:{TEXT}; font-weight:600; padding:0 8px;")
        sb.addWidget(self._status_label, 1)

        self._progress = QProgressBar()
        self._progress.setFixedSize(140, 5)
        self._progress.setTextVisible(False)
        self._progress.setRange(0, 0)   # indeterminate
        self._progress.hide()
        sb.addPermanentWidget(self._progress)

        self._gen_label = _label("", muted=True)
        sb.addPermanentWidget(self._gen_label)

        hotkeys = _label(
            "Enter: загрузить · F5: генерировать · Ctrl+S: отправить · Ctrl+B: в браузер",
            muted=True)
        sb.addPermanentWidget(hotkeys)

    # ═════════════════════════════════════════════════════════════════════════
    #  SHORTCUTS
    # ═════════════════════════════════════════════════════════════════════════

    def _bind_shortcuts(self):
        QShortcut(QKeySequence("F5"),         self).activated.connect(self._generate_hints)
        QShortcut(QKeySequence("Ctrl+S"),     self).activated.connect(self._approve_hints)
        QShortcut(QKeySequence("Ctrl+B"),     self).activated.connect(self._open_in_browser)
        QShortcut(QKeySequence("Ctrl+Return"),self).activated.connect(self._fetch_question)

    # ═════════════════════════════════════════════════════════════════════════
    #  LEFT PANEL: TAB + RENDER TOGGLE
    # ═════════════════════════════════════════════════════════════════════════

    def _switch_tab(self, tab: str):
        self._current_tab = tab
        is_q = (tab == "q")
        # Style active tab button
        active_ss   = f"background:{ACCENT}; color:white; border:none;"
        inactive_ss = f"background:{CARD}; color:{MUTED}; border:1px solid {BORDER};"
        self._tab_q_btn.setStyleSheet(active_ss if is_q else inactive_ss)
        self._tab_s_btn.setStyleSheet(inactive_ss if is_q else active_ss)
        self._show_content()

    def _toggle_render(self):
        if self._render_mode == "tex":
            # Switch to HTML if available for current tab
            has_html = bool(self._question_html if self._current_tab == "q"
                            else self._solution_html)
            if not has_html:
                self._status("Рендер недоступен — HTML не загружен")
                return
            self._render_mode = "html"
            self._render_btn.setText("📄 Исходник")
        else:
            self._render_mode = "tex"
            self._render_btn.setText("🖥 Рендер")
        self._show_content()

    def _show_content(self):
        """Переключает страницу QStackedWidget:
        0 = question tex, 1 = solution tex, 2 = question html, 3 = solution html
        """
        is_q = (self._current_tab == "q")
        use_html = (self._render_mode == "html" and WEBENGINE_OK)

        if use_html:
            idx = 2 if is_q else 3
        else:
            idx = 0 if is_q else 1

        self._left_stack.setCurrentIndex(idx)

    # ═════════════════════════════════════════════════════════════════════════
    #  JWT STATUS
    # ═════════════════════════════════════════════════════════════════════════

    def _update_jwt_label(self):
        token = self.token_entry.text().strip()
        if not token:
            self._jwt_label.setText("")
            return
        try:
            parts = token.split(".")
            if len(parts) != 3:
                self._jwt_label.setText("❓")
                return
            payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
            exp = payload.get("exp")
            if not exp:
                self._jwt_label.setStyleSheet(f"color:{SUCCESS};")
                self._jwt_label.setText("✓ OK")
                return
            rem = exp - datetime.datetime.utcnow().timestamp()
            if rem < 0:
                self._jwt_label.setStyleSheet(f"color:{DANGER};")
                self._jwt_label.setText("✗ истёк")
            elif rem < 3600:
                self._jwt_label.setStyleSheet(f"color:{WARNING};")
                self._jwt_label.setText(f"⚠ {int(rem/60)}м")
            elif rem < 86400:
                self._jwt_label.setStyleSheet(f"color:{SUCCESS};")
                self._jwt_label.setText(f"✓ {int(rem/3600)}ч")
            else:
                self._jwt_label.setStyleSheet(f"color:{SUCCESS};")
                self._jwt_label.setText(f"✓ {int(rem/86400)}д")
        except Exception:
            self._jwt_label.setText("")

    # ═════════════════════════════════════════════════════════════════════════
    #  FETCH QUESTION
    # ═════════════════════════════════════════════════════════════════════════

    def _fetch_question(self):
        qid_str = self.question_id_entry.text().strip()
        if not qid_str.isdigit():
            QMessageBox.warning(self, "Ошибка", "Введите числовой ID задачи")
            return
        token = self.token_entry.text().strip()
        if not token:
            QMessageBox.warning(self, "Ошибка", "Введите JWT токен")
            return

        self._set_loading(True, "Загружаю задачу…")
        self._clear_content()

        def _do():
            qid  = int(qid_str)
            data = fetch_question(qid, token)
            with ThreadPoolExecutor(2) as ex:
                fq = ex.submit(fetch_latex_session, data.get("QuestionTexSessionId",0), token)
                fs = ex.submit(fetch_latex_session, data.get("SolutionTexSessionId",0), token)
                q_s, s_s = fq.result(), fs.result()
            return data, q_s, s_s

        _run(_do,
             on_result=lambda r: self._on_question_loaded(*r),
             on_error=lambda e: self._on_error(_friendly_request_error(Exception(e))))

    def _clear_content(self):
        self.question_title_label.setText("")
        self.question_badge.setText("")
        self.question_tex_view.clear()
        self.solution_tex_view.clear()
        if WEBENGINE_OK:
            self.question_web.setHtml("")
            self.solution_web.setHtml("")
        self.hints_editor.clear()
        self._update_hint_count()
        self._question_data = None

    def _on_question_loaded(self, data, q_s, s_s):
        self._question_data = data
        self._question_html = q_s.get("html", "")
        self._solution_html = s_s.get("html", "")
        self._question_tex  = extract_tex_body(q_s.get("tex", ""))
        self._solution_tex  = extract_tex_body(s_s.get("tex", ""))

        name = data.get("Name", f"Задача #{data['Id']}")
        self.setWindowTitle(f"Школково — #{data['Id']} {name[:50]}")
        self.question_title_label.setText(f"  {name}")
        self.question_title_label.show()

        theme = data.get("ParentThemeId", "")
        if theme:
            self.question_badge.setText(f" Тема: {theme} ")
            self.question_badge.setStyleSheet(
                f"background:{ACCENT}; color:white; border-radius:4px;"
                f" padding:2px 8px; font-size:10px;")
            self.question_badge.show()
        else:
            self.question_badge.hide()

        self.question_tex_view.setText(self._question_tex or "(не загружено)")
        ans = data.get("Answer", {})
        ans_txt = ans.get("text","") if isinstance(ans,dict) else str(ans)
        sol_content = (f"ОТВЕТ: {ans_txt}\n\n" if ans_txt else "") + (self._solution_tex or "(не загружено)")
        self.solution_tex_view.setText(sol_content)

        if WEBENGINE_OK:
            if self._question_html:
                self.question_web.setHtml(self._question_html)
            if self._solution_html:
                self.solution_web.setHtml(self._solution_html)

        existing = data.get("Faq") or []
        if existing:
            self.hints_editor.load_hints(existing)
        else:
            self.hints_editor.clear()
        self._update_hint_count()

        # Auto-render: switch to HTML mode if available
        if WEBENGINE_OK and self._question_html:
            self._render_mode = "html"
            if hasattr(self, "_render_btn"):
                self._render_btn.setText("📄 Исходник")
        else:
            self._render_mode = "tex"
            if hasattr(self, "_render_btn"):
                self._render_btn.setText("🖥 Рендер")

        self._switch_tab("q")   # вернуться на вкладку условия и показать нужный виджет
        self._add_to_history(str(data["Id"]))
        self._task_start_ts = datetime.datetime.now().timestamp()
        self._set_loading(False)

        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._status(f"[{ts}] Задача #{data['Id']} загружена ✓  │  "
                     f"Подсказок на платформе: {len(existing)}")

        if self._batch_running:
            QTimer.singleShot(300, self._on_batch_question_ready)

    # ═════════════════════════════════════════════════════════════════════════
    #  GENERATE HINTS
    # ═════════════════════════════════════════════════════════════════════════

    def _generate_hints(self):
        if not self._question_data:
            QMessageBox.warning(self, "Внимание", "Сначала загрузите задачу")
            return
        api_key = self.api_key_entry.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Ошибка", "Введите Groq API Key")
            return

        prompt    = self.prompt_text.toPlainText().strip()
        model     = self.model_combo.currentText()
        temp      = self._temp_slider.value() / 100.0
        existing  = self.hints_editor.get_hints()
        ref_q     = self._ref_question
        ref_h     = self._ref_hints

        self._set_loading(True,
            f"Генерирую подсказки [{model.split('/')[-1]}, t={temp:.2f}]…"
            + (" + эталон" if ref_h else ""))

        def _do():
            return generate_hints_groq(
                question_text=self._question_tex,
                solution_text=self._solution_tex,
                existing_hints=existing,
                system_prompt=prompt,
                api_key=api_key,
                model=model,
                temperature=temp,
                reference_question=ref_q if ref_h else None,
                reference_hints=ref_h if ref_h else None,
            )

        _run(_do,
             on_result=self._on_hints_generated,
             on_error=self._on_error)

    def _on_hints_generated(self, hints: list):
        self.hints_editor.load_hints(hints)
        self._update_hint_count()
        self._gen_count += 1
        self._gen_label.setText(f"генераций: {self._gen_count}")
        self._set_loading(False)
        batch_note = (f"  │  Пакет: осталось {len(self._batch_queue)}"
                      if self._batch_running else "")
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._status(f"[{ts}] Сгенерировано {len(hints)} подсказок. "
                     f"Проверьте и нажмите «Отправить».{batch_note}")

    # ═════════════════════════════════════════════════════════════════════════
    #  SINGLE HINT REGEN
    # ═════════════════════════════════════════════════════════════════════════

    def _regen_single_hint(self, idx: int):
        if not self._question_data:
            return
        api_key = self.api_key_entry.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Ошибка", "Введите Groq API Key")
            return

        all_hints = self.hints_editor.get_hints()
        others    = [h for i, h in enumerate(all_hints) if i != idx]
        prompt    = self.prompt_text.toPlainText().strip()
        model     = self.model_combo.currentText()
        temp      = self._temp_slider.value() / 100.0

        regen_prompt = (
            f"Перепиши только подсказку №{idx+1}. "
            f"Остальные {len(others)} подсказок уже готовы — учти их уровень. "
            'Верни JSON-массив с ОДНИМ элементом: [["Заголовок","Шаг 1",...]]'
        )

        self._set_loading(True, f"🔄 Регенерирую подсказку №{idx+1}…")

        def _do():
            return generate_hints_groq(
                question_text=self._question_tex,
                solution_text=self._solution_tex,
                existing_hints=others,
                system_prompt=prompt + "\n\n" + regen_prompt,
                api_key=api_key,
                model=model,
                temperature=temp,
            )

        def _done(result):
            new_hint = result[0] if result and isinstance(result[0], list) else result
            self.hints_editor.update_card(idx, new_hint)
            self._set_loading(False)
            self._status(f"✅ Подсказка №{idx+1} перегенерирована")

        _run(_do, on_result=_done, on_error=self._on_error)

    # ═════════════════════════════════════════════════════════════════════════
    #  APPROVE (SEND TO PLATFORM)
    # ═════════════════════════════════════════════════════════════════════════

    def _approve_hints(self):
        if not self._question_data:
            QMessageBox.warning(self, "Внимание", "Сначала загрузите задачу")
            return
        hints = self.hints_editor.get_hints()
        if not hints:
            QMessageBox.warning(self, "Внимание", "Нет подсказок для отправки")
            return

        empty = [i+1 for i, h in enumerate(hints) if not any(p.strip() for p in h)]
        if empty:
            ans = QMessageBox.question(
                self, "Пустые подсказки",
                f"Подсказки №{', '.join(map(str,empty))} не заполнены.\nОтправить всё равно?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ans != QMessageBox.StandardButton.Yes:
                return

        qid   = self._question_data["Id"]
        token = self.token_entry.text().strip()
        if not token:
            QMessageBox.warning(self, "Ошибка", "Введите JWT токен")
            return

        if not self._batch_running:
            ans = QMessageBox.question(
                self, "Подтверждение",
                f"Отправить {len(hints)} подсказок для задачи #{qid}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ans != QMessageBox.StandardButton.Yes:
                return

        self._set_loading(True, "Сохраняю подсказки…")

        def _do():
            save_hints_to_platform(qid, hints, self._question_data, token)
            return len(hints)

        _run(_do, on_result=self._on_saved, on_error=self._on_error)

    def _on_saved(self, hints_count: int):
        self._set_loading(False)
        elapsed = datetime.datetime.now().timestamp() - self._task_start_ts
        self._log_entry(ok=True, hints_count=hints_count)
        self._update_stats(elapsed)

        ts = datetime.datetime.now().strftime("%H:%M:%S")

        if self._batch_running and self._batch_queue:
            done = self._batch_total - len(self._batch_queue)
            self._status(f"[{ts}] ✅ #{done}/{self._batch_total} сохранено — следующая…")
            QTimer.singleShot(400, self._batch_next)

        elif self._batch_running and not self._batch_queue:
            self._batch_running = False
            self._batch_btn.setText("▶ Запустить пакет")
            self._batch_btn.setProperty("accent2", "true")
            self._status(f"[{ts}] ✅ Пакет завершён — {self._batch_total} задач!")
            QMessageBox.information(self, "Пакет завершён",
                                    f"Все {self._batch_total} задач обработаны!")
        else:
            self._status(f"[{ts}] ✅ Подсказки успешно сохранены")
            QMessageBox.information(self, "Готово", "Подсказки отправлены на платформу!")
            # Auto-next checkbox removed — use batch mode for sequential processing

    # ═════════════════════════════════════════════════════════════════════════
    #  BATCH
    # ═════════════════════════════════════════════════════════════════════════

    def _parse_batch_ids(self, text: str) -> list[str]:
        text = text.strip()
        m = re.match(r'^(\d+)\s*[-–]\s*(\d+)$', text)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a <= b <= a + 500:
                return [str(i) for i in range(a, b+1)]
        return [p.strip() for p in re.split(r'[,\s]+', text) if p.strip().isdigit()]

    def _start_batch(self):
        if self._batch_running:
            self._batch_running = False
            self._batch_queue.clear()
            self._batch_btn.setText("▶ Запустить пакет")
            self._reset_batch_btn_style()
            self._batch_status.setText("Пакет остановлен")
            if hasattr(self, "_batch_progress_bar"):
                self._batch_progress_bar.setVisible(False)
            return

        raw = self.batch_entry.text().strip()
        if not raw:
            QMessageBox.warning(self, "Пакет", "Введите список или диапазон ID")
            return
        if not self.token_entry.text().strip():
            QMessageBox.warning(self, "Ошибка", "Введите JWT токен")
            return

        ids = self._parse_batch_ids(raw)
        if not ids:
            QMessageBox.warning(self, "Пакет",
                "Не удалось распознать ID.\nПример: 101599-101605  или  101599, 101600")
            return

        if len(ids) > 200:
            ans = QMessageBox.question(self, "Пакет",
                f"Будет обработано {len(ids)} задач. Продолжить?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ans != QMessageBox.StandardButton.Yes:
                return

        self._batch_queue = ids
        self._batch_total = len(ids)
        self._batch_running = True
        self._batch_btn.setText("⏹ Остановить")
        self._batch_btn.setProperty("accent2", "false")
        self._batch_btn.setProperty("danger",  "true")
        self._batch_btn.style().unpolish(self._batch_btn)
        self._batch_btn.style().polish(self._batch_btn)
        if hasattr(self, "_batch_progress_bar"):
            self._batch_progress_bar.setMaximum(len(ids))
            self._batch_progress_bar.setValue(0)
            self._batch_progress_bar.setVisible(True)
        self._batch_next()

    def _batch_next(self):
        if not self._batch_running or not self._batch_queue:
            self._batch_running = False
            self._batch_btn.setText("▶ Запустить пакет")
            self._reset_batch_btn_style()
            done = self._batch_total
            self._batch_status.setText(f"✅ Пакет завершён ({done} задач)")
            self._update_batch_progress(done)
            return

        qid = self._batch_queue.pop(0)
        done = self._batch_total - len(self._batch_queue)
        self._batch_status.setText(f"Задача {done}/{self._batch_total}: #{qid}")
        self._update_batch_progress(done - 1)   # показываем прогресс до текущей
        self.question_id_entry.setText(qid)
        self._fetch_question()

    def _update_batch_progress(self, done: int):
        """Обновляет прогресс-бар пакетного режима в заголовке."""
        if not hasattr(self, "_batch_progress_bar"):
            return
        if self._batch_total > 0:
            self._batch_progress_bar.setMaximum(self._batch_total)
            self._batch_progress_bar.setValue(done)
            self._batch_progress_bar.setVisible(self._batch_running or done > 0)
        else:
            self._batch_progress_bar.setVisible(False)

    def _reset_batch_btn_style(self):
        self._batch_btn.setProperty("danger", "false")
        self._batch_btn.setProperty("accent2", "true")
        self._batch_btn.style().unpolish(self._batch_btn)
        self._batch_btn.style().polish(self._batch_btn)

    def _batch_skip(self):
        if not self._batch_running:
            return
        if not self._batch_queue:
            self._batch_running = False
            self._batch_btn.setText("▶ Запустить пакет")
            self._batch_status.setText("✅ Пакет завершён")
            return
        qid = self._question_data["Id"] if self._question_data else "?"
        self._log_entry(ok=False, hints_count=0)
        self._status(f"⏭ Задача #{qid} пропущена")
        QTimer.singleShot(200, self._batch_next)

    def _on_batch_question_ready(self):
        if self._batch_running:
            self._generate_hints()

    # ═════════════════════════════════════════════════════════════════════════
    #  THEME QUEUE
    # ═════════════════════════════════════════════════════════════════════════

    def _open_theme_dialog(self):
        if not self.token_entry.text().strip():
            QMessageBox.warning(self, "Ошибка", "Введите JWT токен")
            return
        dlg = ThemeQueueDialog(self, self._load_theme_queue)
        dlg.queue_ready.connect(self._on_theme_queue_loaded)
        dlg.exec()

    def _load_theme_queue(self, theme_id: int, limit: int, callback):
        token = self.token_entry.text().strip()
        def _do():
            return fetch_questions_without_hints(theme_id, token, limit)
        def _done(questions):
            callback(questions)
        def _err(e):
            callback([], e)
        _run(_do, on_result=_done, on_error=_err)

    def _on_theme_queue_loaded(self, ids: list):
        self.batch_entry.setText(", ".join(ids[:200]))
        self._status(f"📂 Тема: загружено {len(ids)} задач без подсказок")

    # ═════════════════════════════════════════════════════════════════════════
    #  PROMPT PROFILES
    # ═════════════════════════════════════════════════════════════════════════

    def _on_profile_select(self, name: str):
        if name and name != "(выбрать профиль)" and name in self._prompt_profiles:
            self.prompt_text.setText(self._prompt_profiles[name])
            self._status(f"📄 Загружен профиль «{name}»")

    def _save_profile(self):
        name = ask_text(self, "Сохранить профиль", "Введите название профиля:")
        if not name:
            return
        self._prompt_profiles[name] = self.prompt_text.toPlainText()
        self._refresh_profiles()
        self._profile_combo.setCurrentText(name)
        self._save_settings()
        self._status(f"✅ Профиль «{name}» сохранён")

    def _delete_profile(self):
        name = self._profile_combo.currentText()
        if name == "(выбрать профиль)" or name not in self._prompt_profiles:
            return
        ans = QMessageBox.question(self, "Удалить профиль", f"Удалить «{name}»?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ans == QMessageBox.StandardButton.Yes:
            del self._prompt_profiles[name]
            self._refresh_profiles()
            self._save_settings()

    def _refresh_profiles(self):
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        self._profile_combo.addItem("(выбрать профиль)")
        self._profile_combo.addItems(list(self._prompt_profiles.keys()))
        self._profile_combo.blockSignals(False)

    # ═════════════════════════════════════════════════════════════════════════
    #  REFERENCE TASK
    # ═════════════════════════════════════════════════════════════════════════

    def _load_reference(self):
        ref_id = self._ref_id_edit.text().strip()
        if not ref_id.isdigit():
            QMessageBox.warning(self, "Эталон", "Введите числовой ID")
            return
        token = self.token_entry.text().strip()
        def _do():
            data  = fetch_question(int(ref_id), token)
            q_s   = fetch_latex_session(data.get("QuestionTexSessionId",0), token)
            return data, q_s
        def _done(r):
            data, q_s = r
            self._ref_question = extract_tex_body(q_s.get("tex",""))
            self._ref_hints    = data.get("Faq") or []
            self._ref_status.setText(f"#{data['Id']} — {len(self._ref_hints)} подсказок")
            self._ref_status.setStyleSheet(f"color:{SUCCESS};")
        _run(_do, on_result=_done, on_error=lambda e: self._status(f"❌ Эталон: {e}"))

    def _clear_reference(self):
        self._ref_question = ""
        self._ref_hints    = []
        self._ref_status.setText("не загружена")
        self._ref_status.setStyleSheet(f"color:{MUTED};")

    # ═════════════════════════════════════════════════════════════════════════
    #  PROMPT HELPERS
    # ═════════════════════════════════════════════════════════════════════════

    def _reset_prompt(self):
        ans = QMessageBox.question(self, "Сброс промпта",
            "Сбросить промпт к значению по умолчанию?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ans == QMessageBox.StandardButton.Yes:
            self.prompt_text.setText(self._default_prompt())

    def _load_prompt_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Открыть промпт", "",
            "Текстовые файлы (*.txt);;Все файлы (*.*)")
        if path:
            with open(path, encoding="utf-8") as f:
                self.prompt_text.setText(f.read())
            self._status(f"Промпт загружен: {os.path.basename(path)}")

    def _save_prompt_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить промпт", "prompt.txt",
            "Текстовые файлы (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.prompt_text.toPlainText())
            self._status(f"Промпт сохранён: {os.path.basename(path)}")

    def _update_char_count(self):
        n = len(self.prompt_text.toPlainText())
        self._char_label.setText(f"{n} симв.")

    def _on_temp_change(self, val: int):
        self._temp_label.setText(f"{val/100:.2f}")

    # ═════════════════════════════════════════════════════════════════════════
    #  HINTS HELPERS
    # ═════════════════════════════════════════════════════════════════════════

    def _update_hint_count(self):
        self._hint_count_label.setText(f"({self.hints_editor.count()})")

    def _copy_json(self):
        hints = self.hints_editor.get_hints()
        if not hints:
            QMessageBox.information(self, "Нет данных", "Подсказок нет")
            return
        QApplication.clipboard().setText(
            json.dumps(hints, ensure_ascii=False, indent=2))
        self._status("📋 JSON скопирован в буфер")

    def _show_preview(self):
        hints = self.hints_editor.get_hints()
        if not hints:
            QMessageBox.information(self, "Нет данных", "Подсказок нет")
            return
        name = self._question_data.get("Name","") if self._question_data else ""
        HintPreviewDialog(self, hints, name).exec()

    # ═════════════════════════════════════════════════════════════════════════
    #  HISTORY
    # ═════════════════════════════════════════════════════════════════════════

    def _add_to_history(self, qid: str):
        if qid in self._id_history:
            self._id_history.remove(qid)
        self._id_history.insert(0, qid)
        self._id_history = self._id_history[:MAX_HISTORY]
        self.history_combo.blockSignals(True)
        self.history_combo.clear()
        self.history_combo.addItem("(история)")
        self.history_combo.addItems(self._id_history)
        self.history_combo.blockSignals(False)

    def _on_history_select(self, text: str):
        if text and text != "(история)" and text.isdigit():
            self.question_id_entry.setText(text)
            self._fetch_question()

    # ═════════════════════════════════════════════════════════════════════════
    #  MODELS
    # ═════════════════════════════════════════════════════════════════════════

    def _fetch_models(self):
        api_key = self.api_key_entry.text().strip()
        def _do():
            return fetch_free_models_from_groq(api_key)
        def _done(models):
            current = self.model_combo.currentText()
            self.model_combo.blockSignals(True)
            self.model_combo.clear()
            self.model_combo.addItems(models)
            if current in models:
                self.model_combo.setCurrentText(current)
            self.model_combo.blockSignals(False)
            self._status(f"Загружено {len(models)} моделей")
        _run(_do, on_result=_done)

    # ═════════════════════════════════════════════════════════════════════════
    #  SETTINGS
    # ═════════════════════════════════════════════════════════════════════════

    def _open_settings(self):
        cur = {
            "token":      self.token_entry.text(),
            "api_key":    self.api_key_entry.text(),
            "proxy":      self._settings.get("proxy",""),
            "verify_ssl": self._settings.get("verify_ssl", True),
        }
        dlg = SettingsDialog(self, cur)
        dlg.saved.connect(self._apply_settings)
        dlg.exec()

    def _apply_settings(self, data: dict):
        if data.get("token"):
            self.token_entry.setText(data["token"])
        if data.get("api_key"):
            self.api_key_entry.setText(data["api_key"])
        if data.get("proxy"):
            self._settings["proxy"] = data["proxy"]
            set_proxy(data["proxy"])
        verify = data.get("verify_ssl", True)
        self._settings["verify_ssl"] = verify
        _apply_ssl(verify)
        self._save_settings()
        QTimer.singleShot(100, self._update_jwt_label)

    def _save_settings(self):
        data = {
            "token":           self.token_entry.text(),
            "api_key":         self.api_key_entry.text(),
            "model":           self.model_combo.currentText(),
            "prompt":          self.prompt_text.toPlainText(),
            "temperature":     self._temp_slider.value(),
            "proxy":           self._settings.get("proxy",""),
            "verify_ssl":      self._settings.get("verify_ssl", True),
            "history":         self._id_history,
            "prompt_profiles": self._prompt_profiles,
        }
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._status("Настройки сохранены")
        except Exception as e:
            self._status(f"❌ Не удалось сохранить настройки: {e}")

    def _load_settings(self):
        env_token = os.getenv("SHKOLKOVO_TOKEN","")
        env_key   = os.getenv("GROQ_API_KEY","")
        if env_token: self.token_entry.setText(env_token)
        if env_key:   self.api_key_entry.setText(env_key)

        if not os.path.exists(SETTINGS_FILE):
            self._fetch_models()
            return
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                data = json.load(f)
            if not env_token and data.get("token"):
                self.token_entry.setText(data["token"])
            if not env_key and data.get("api_key"):
                self.api_key_entry.setText(data["api_key"])
            if data.get("model"):
                idx = self.model_combo.findText(data["model"])
                if idx >= 0: self.model_combo.setCurrentIndex(idx)
            if data.get("prompt"):
                self.prompt_text.setText(data["prompt"])
            if data.get("temperature") is not None:
                self._temp_slider.setValue(int(data["temperature"]))
            if data.get("proxy"):
                self._settings["proxy"] = data["proxy"]
                set_proxy(data["proxy"])
            _apply_ssl(data.get("verify_ssl", True))
            self._settings["verify_ssl"] = data.get("verify_ssl", True)
            if data.get("history"):
                self._id_history = data["history"][:MAX_HISTORY]
                self.history_combo.addItems(self._id_history)
            if data.get("prompt_profiles"):
                self._prompt_profiles = data["prompt_profiles"]
                self._refresh_profiles()
        except Exception:
            pass
        self._fetch_models()
        QTimer.singleShot(300, self._update_jwt_label)

    # ═════════════════════════════════════════════════════════════════════════
    #  LOG
    # ═════════════════════════════════════════════════════════════════════════

    def _load_log(self):
        try:
            self._process_log = self._log_store.load_for_day()
        except Exception:
            self._process_log = []

    def _log_entry(self, ok: bool, hints_count: int = 0):
        if not self._question_data:
            return
        entry = {
            "date":  datetime.date.today().isoformat(),
            "ts":    datetime.datetime.now().strftime("%H:%M:%S"),
            "id":    str(self._question_data.get("Id","")),
            "name":  self._question_data.get("Name","")[:60],
            "hints": hints_count,
            "ok":    ok,
        }
        self._process_log.append(entry)
        try: self._log_store.append(entry)
        except Exception: pass

    def _show_log(self):
        dlg = LogDialog(self, self._process_log)
        dlg.exec()

    def _update_stats(self, elapsed: float = 0):
        self._tasks_done += 1
        if elapsed > 0:
            self._task_times.append(elapsed)
        avg = sum(self._task_times)/len(self._task_times) if self._task_times else 0
        avg_str = f"{avg:.0f}с" if avg < 60 else f"{avg/60:.1f}м"
        self._stats_label.setText(f"✅ {self._tasks_done}  ⏱ {avg_str}")

    # ═════════════════════════════════════════════════════════════════════════
    #  MISC
    # ═════════════════════════════════════════════════════════════════════════

    def _open_in_browser(self):
        qid = self.question_id_entry.text().strip()
        if qid.isdigit():
            webbrowser.open(
                f"https://1.shkolkovo.online/admin/homework/question?QuestionId={qid}")

    def _status(self, txt: str):
        self._status_label.setText(txt)

    def _set_loading(self, loading: bool, msg: str = ""):
        for b in (self.fetch_btn, self.generate_btn,
                  self.approve_btn, self.retry_btn):
            b.setEnabled(not loading)
        if msg: self._status(msg)
        if loading:
            self._progress.show()
        else:
            self._progress.hide()

    def _on_error(self, msg: str):
        if self._batch_running:
            self._set_loading(False)
            qid = self._question_data["Id"] if self._question_data else "?"
            done = self._batch_total - len(self._batch_queue)
            self._log_entry(ok=False, hints_count=0)
            # В пакетном режиме — всегда пропускаем задачу и продолжаем.
            # Никаких диалогов, которые тормозили бы обработку.
            self._status(
                f"⚠ #{qid} ({done}/{self._batch_total}) пропущена: "
                f"{msg[:80]} — продолжаю…")
            self._update_batch_progress(done)
            QTimer.singleShot(400, self._batch_next)
            return
        self._set_loading(False)
        self._status(f"❌ {msg}")
        QMessageBox.critical(self, "Ошибка", msg)

    def closeEvent(self, event):
        try: self._save_settings()
        except Exception: pass
        super().closeEvent(event)

    @staticmethod
    def _default_prompt() -> str:
        return (
            "Ты методист образовательной платформы для подготовки к ЕГЭ.\n\n"
            "Твоя задача — написать 4‑5 подсказок к задаче. Подсказки должны:\n"
            "- Вести ученика к решению постепенно, не раскрывая ответ\n"
            "- Быть в форме наводящих вопросов или маленьких шагов\n"
            "- Каждая подсказка — более детальная версия предыдущей\n"
            "- Использовать простой и понятный язык\n\n"
            "Формат ответа — строго JSON, массив массивов строк:\n"
            '[\n  ["Подсказка 1", "Вопрос…"],\n  ["Подсказка 2", "Шаг 1", "Вопрос…"],\n  …\n]\n\n'
            "ВАЖНО: Верни ТОЛЬКО JSON без пояснений и markdown."
        )
