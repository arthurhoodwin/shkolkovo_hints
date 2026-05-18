from __future__ import annotations

import json
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .api import _friendly_request_error
from .app_qt import App as HintsApp
from .app_qt import _run
from .task_client_api import (
    create_question_draft,
    get_question_by_id,
    list_difficulties,
    list_questions,
    list_tags,
    list_themes,
    patch_question_from_form,
    update_question,
    update_related_questions,
)

SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".shkolkovo_full_client.json")


ANSWER_TYPE_ITEMS = [
    ("1 — Простой (точное совпадение)", 1, 1),
    ("20 — Табличный (1 в 1)", 20, 3),
    ("21 — Табличные пары", 21, 3),
    ("24 — Табличный (допустимы лишние пустые строки)", 24, 3),
]


def _to_optional_int(text: str) -> int | None:
    value = text.strip()
    if not value:
        return None
    return int(value)


def _parse_id_list(text: str) -> list[int]:
    raw = text.replace(";", ",").replace("\n", ",")
    result: list[int] = []
    for part in raw.split(","):
        p = part.strip()
        if not p:
            continue
        result.append(int(p))
    return result


def _parse_table_text(text: str, rows: int, cols: int) -> list[list[str]]:
    matrix = [["" for _ in range(cols)] for _ in range(rows)]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for r, line in enumerate(lines[:rows]):
        parts = [p.strip() for p in line.split(",")]
        for c, value in enumerate(parts[:cols]):
            matrix[r][c] = value
    return matrix


def _table_to_text(table: QTableWidget) -> str:
    lines: list[str] = []
    for r in range(table.rowCount()):
        row_values: list[str] = []
        for c in range(table.columnCount()):
            item = table.item(r, c)
            row_values.append(item.text().strip() if item else "")
        if any(value for value in row_values):
            lines.append(",".join(row_values))
    return "\n".join(lines)


class FullClientApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Школково — Клиент базы задач")
        self.resize(1640, 960)
        self.setMinimumSize(1320, 780)

        self._current_question: dict | None = None
        self._last_items: list[dict] = []
        self._hints_window: HintsApp | None = None

        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        layout.addWidget(self._build_topbar())

        main_tabs = QTabWidget()
        main_tabs.addTab(self._build_workbench(), "База задач")
        main_tabs.addTab(self._build_tools_tab(), "Инструменты")
        layout.addWidget(main_tabs, 1)

        self._status = QLabel("Готово")
        bar = QStatusBar()
        bar.addWidget(self._status)
        self.setStatusBar(bar)

    def _build_topbar(self) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        row.addWidget(QLabel("JWT токен:"))
        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_edit.setPlaceholderText("eyJ...")
        row.addWidget(self.token_edit, 1)

        self.load_refs_btn = QPushButton("Загрузить справочники")
        self.load_refs_btn.clicked.connect(self._load_reference_data)
        row.addWidget(self.load_refs_btn)

        self.save_settings_btn = QPushButton("Сохранить настройки")
        self.save_settings_btn.clicked.connect(self._save_settings)
        row.addWidget(self.save_settings_btn)
        return box

    def _build_workbench(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([700, 920])
        layout.addWidget(splitter, 1)
        return wrapper

    def _build_tools_tab(self) -> QWidget:
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(16, 16, 16, 16)
        col.setSpacing(12)

        title = QLabel("Дополнительные окна")
        title.setStyleSheet("font-size:18px; font-weight:700;")
        col.addWidget(title)

        info = QLabel(
            "Здесь можно открыть окно генератора подсказок. "
            "Оно работает параллельно с клиентом базы задач."
        )
        info.setWordWrap(True)
        info.setStyleSheet("font-size:13px; color:#9fb0c8;")
        col.addWidget(info)

        btn = QPushButton("Открыть генератор подсказок")
        btn.setProperty("accent", "true")
        btn.clicked.connect(self._open_hints_window)
        btn.setFixedHeight(38)
        col.addWidget(btn, 0, Qt.AlignmentFlag.AlignLeft)
        col.addStretch()
        return page

    def _build_left_panel(self) -> QWidget:
        wrapper = QWidget()
        col = QVBoxLayout(wrapper)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(10)

        filters = QGroupBox("Поиск и создание задач")
        grid = QGridLayout(filters)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        self.f_qid = QLineEdit()
        self.f_qid.setPlaceholderText("ID задачи")
        self.f_theme = QLineEdit()
        self.f_theme.setPlaceholderText("ID темы")
        self.f_diff = QLineEdit()
        self.f_diff.setPlaceholderText("ID сложности")
        self.f_page = QLineEdit("1")
        self.f_per_page = QLineEdit("50")

        self.f_private = QComboBox()
        self.f_private.addItems(["Любая приватность", "Только публичные", "Только приватные"])
        self.f_deactivated = QComboBox()
        self.f_deactivated.addItems(["Любой статус", "Только активные", "Только деактивированные"])

        self.f_new_name = QLineEdit("Новая задача")
        self.f_new_source = QLineEdit()
        self.f_new_source.setPlaceholderText("ID источника (опционально)")

        grid.addWidget(QLabel("ID задачи"), 0, 0)
        grid.addWidget(self.f_qid, 0, 1)
        grid.addWidget(QLabel("ID темы"), 0, 2)
        grid.addWidget(self.f_theme, 0, 3)

        grid.addWidget(QLabel("Сложность"), 1, 0)
        grid.addWidget(self.f_diff, 1, 1)
        grid.addWidget(QLabel("Приватность"), 1, 2)
        grid.addWidget(self.f_private, 1, 3)

        grid.addWidget(QLabel("Статус"), 2, 0)
        grid.addWidget(self.f_deactivated, 2, 1)
        grid.addWidget(QLabel("Страница"), 2, 2)
        grid.addWidget(self.f_page, 2, 3)

        grid.addWidget(QLabel("На страницу"), 3, 0)
        grid.addWidget(self.f_per_page, 3, 1)
        self.search_btn = QPushButton("Показать")
        self.search_btn.setProperty("accent", "true")
        self.search_btn.clicked.connect(self._search)
        grid.addWidget(self.search_btn, 3, 3)

        grid.addWidget(QLabel("Новая задача"), 4, 0)
        grid.addWidget(self.f_new_name, 4, 1, 1, 2)
        grid.addWidget(self.f_new_source, 4, 3)

        self.create_btn = QPushButton("Создать черновик")
        self.create_btn.clicked.connect(self._create_draft)
        grid.addWidget(self.create_btn, 4, 4)
        col.addWidget(filters)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Название", "Тема", "Сложность", "Приватная", "Деактив.", "Обновлена"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellDoubleClicked.connect(self._open_from_table)
        col.addWidget(self.table, 1)
        return wrapper

    def _build_right_panel(self) -> QWidget:
        wrapper = QWidget()
        col = QVBoxLayout(wrapper)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(10)

        header = QHBoxLayout()
        self.current_label = QLabel("Задача: не загружена")
        self.current_label.setStyleSheet("font-size:16px; font-weight:700;")
        header.addWidget(self.current_label)
        header.addStretch()

        self.reload_btn = QPushButton("Обновить")
        self.reload_btn.clicked.connect(self._reload_current)
        header.addWidget(self.reload_btn)

        self.save_btn = QPushButton("Сохранить на платформу")
        self.save_btn.setProperty("success", "true")
        self.save_btn.clicked.connect(self._save_current)
        header.addWidget(self.save_btn)
        col.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_tab_main(), "Основное")
        self.tabs.addTab(self._build_tab_answer(), "Ответ")
        self.tabs.addTab(self._build_tab_hints(), "Подсказки")
        self.tabs.addTab(self._build_tab_related(), "Связи")
        self.tabs.addTab(self._build_tab_json(), "JSON")
        col.addWidget(self.tabs, 1)
        return wrapper

    def _build_tab_main(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        self.e_name = QLineEdit()
        self.e_parent_theme = QLineEdit()
        self.e_difficulty = QLineEdit()
        self.e_source = QLineEdit()
        self.e_sort_order = QLineEdit()
        self.e_lesson_time = QLineEdit()
        self.e_themes = QLineEdit()
        self.e_tags = QLineEdit()
        self.e_private = QCheckBox("Приватная задача")
        self.e_deactivated = QCheckBox("Деактивирована")

        form.addRow("Название", self.e_name)
        form.addRow("ParentThemeId", self.e_parent_theme)
        form.addRow("DifficultyId", self.e_difficulty)
        form.addRow("SourceId", self.e_source)
        form.addRow("SortOrder", self.e_sort_order)
        form.addRow("LessonTimeCode", self.e_lesson_time)
        form.addRow("Themes (через запятую)", self.e_themes)
        form.addRow("Tags (через запятую)", self.e_tags)
        form.addRow(self.e_private)
        form.addRow(self.e_deactivated)
        return page

    def _build_tab_answer(self) -> QWidget:
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(8, 8, 8, 8)
        col.setSpacing(10)

        form = QFormLayout()
        self.e_answer_type = QComboBox()
        for title, answer_type, input_type in ANSWER_TYPE_ITEMS:
            self.e_answer_type.addItem(title, (answer_type, input_type))
        self.e_answer_type.currentIndexChanged.connect(self._on_answer_type_changed)

        self.e_input_type = QLineEdit()
        self.e_input_type.setReadOnly(True)
        self.e_ap_length = QLineEdit()
        self.e_ap_height = QLineEdit()
        self.e_answer_needs_file = QCheckBox("Ответ требует приложенный файл")
        self.e_answer_is_proof = QCheckBox("Ответ является доказательством")
        self.e_wrong_answers = QPlainTextEdit()
        self.e_wrong_answers.setMinimumHeight(80)

        form.addRow("Тип ответа", self.e_answer_type)
        form.addRow("InputType", self.e_input_type)
        form.addRow("AnswerProperty.length", self.e_ap_length)
        form.addRow("AnswerProperty.height", self.e_ap_height)
        form.addRow(self.e_answer_needs_file)
        form.addRow(self.e_answer_is_proof)
        form.addRow("Неверные ответы (по строкам)", self.e_wrong_answers)
        col.addLayout(form)

        answer_tabs = QTabWidget()
        self.answer_text_box = QPlainTextEdit()
        self.answer_text_box.setPlaceholderText("Например: 4484,356")
        answer_tabs.addTab(self.answer_text_box, "Текст")

        table_tab = QWidget()
        tcol = QVBoxLayout(table_tab)
        tcol.setContentsMargins(8, 8, 8, 8)
        tcol.setSpacing(8)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Столбцы:"))
        self.tbl_cols = QSpinBox()
        self.tbl_cols.setRange(1, 12)
        self.tbl_cols.setValue(2)
        controls.addWidget(self.tbl_cols)
        controls.addWidget(QLabel("Строки:"))
        self.tbl_rows = QSpinBox()
        self.tbl_rows.setRange(1, 40)
        self.tbl_rows.setValue(1)
        controls.addWidget(self.tbl_rows)

        self.btn_resize_table = QPushButton("Применить размер")
        self.btn_resize_table.clicked.connect(self._resize_answer_table)
        controls.addWidget(self.btn_resize_table)

        self.btn_text_to_table = QPushButton("Текст → Таблица")
        self.btn_text_to_table.clicked.connect(self._answer_text_to_table)
        controls.addWidget(self.btn_text_to_table)

        self.btn_table_to_text = QPushButton("Таблица → Текст")
        self.btn_table_to_text.clicked.connect(self._answer_table_to_text)
        controls.addWidget(self.btn_table_to_text)
        controls.addStretch()
        tcol.addLayout(controls)

        self.answer_table = QTableWidget(1, 2)
        self.answer_table.horizontalHeader().setStretchLastSection(True)
        tcol.addWidget(self.answer_table, 1)
        answer_tabs.addTab(table_tab, "Таблица")

        col.addWidget(answer_tabs, 1)

        hint = QLabel(
            "Типы из HAR: 20/21/24 используют InputType=3 и табличный формат в Answer.text. "
            "Хранилище — текст, таблица нужна для удобного редактирования."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size:11px; color:#9fb0c8;")
        col.addWidget(hint)
        self._on_answer_type_changed()
        return page

    def _build_tab_hints(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(8, 8, 8, 8)
        self.e_faq_json = QPlainTextEdit()
        self.e_faq_json.setPlaceholderText(
            '[["Подсказка 1", "Шаг 1"], ["Подсказка 2", "Шаг 1", "Шаг 2"]]'
        )
        lay.addWidget(QLabel("Faq JSON (массив массивов строк):"))
        lay.addWidget(self.e_faq_json, 1)
        return page

    def _build_tab_related(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(8, 8, 8, 8)
        self.e_related = QLineEdit()
        self.e_related.setPlaceholderText("ID связанных задач через запятую")
        lay.addWidget(QLabel("RelatedQuestionIds:"))
        lay.addWidget(self.e_related)
        lay.addStretch()
        return page

    def _build_tab_json(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(8, 8, 8, 8)

        row = QHBoxLayout()
        self.btn_refresh_json = QPushButton("Обновить JSON из формы")
        self.btn_refresh_json.clicked.connect(self._refresh_raw_json_from_form)
        self.btn_apply_json = QPushButton("Применить JSON в форму")
        self.btn_apply_json.clicked.connect(self._apply_raw_json_to_form)
        row.addWidget(self.btn_refresh_json)
        row.addWidget(self.btn_apply_json)
        row.addStretch()
        lay.addLayout(row)

        self.raw_json = QPlainTextEdit()
        lay.addWidget(self.raw_json, 1)
        return page

    def _resize_answer_table(self):
        self.answer_table.setColumnCount(self.tbl_cols.value())
        self.answer_table.setRowCount(self.tbl_rows.value())

    def _answer_text_to_table(self):
        self._resize_answer_table()
        matrix = _parse_table_text(
            self.answer_text_box.toPlainText(),
            self.answer_table.rowCount(),
            self.answer_table.columnCount(),
        )
        for r in range(self.answer_table.rowCount()):
            for c in range(self.answer_table.columnCount()):
                self.answer_table.setItem(r, c, QTableWidgetItem(matrix[r][c]))

    def _answer_table_to_text(self):
        self.answer_text_box.setPlainText(_table_to_text(self.answer_table))

    def _search(self):
        try:
            token = self._token()
            question_id = _to_optional_int(self.f_qid.text())
            theme_id = _to_optional_int(self.f_theme.text())
            difficulty_id = _to_optional_int(self.f_diff.text())
            page = int(self.f_page.text().strip() or "1")
            per_page = int(self.f_per_page.text().strip() or "50")
        except Exception as exc:
            self._error(f"Некорректные фильтры: {exc}")
            return

        privacy = self.f_private.currentIndex()
        is_private = None if privacy == 0 else privacy == 2
        deactivated = self.f_deactivated.currentIndex()
        is_deactivated = None if deactivated == 0 else deactivated == 2

        self._set_status("Загрузка списка задач...")

        def _do():
            return list_questions(
                token,
                page=page,
                per_page=per_page,
                question_id=question_id,
                parent_theme_id=theme_id,
                difficulty_id=difficulty_id,
                is_private=is_private,
                is_deactivated=is_deactivated,
            )

        def _done(data):
            items, _payload = data
            self._last_items = items
            self._fill_table(items)
            self._set_status(f"Загружено задач: {len(items)}")

        _run(_do, on_result=_done, on_error=lambda e: self._error(_friendly_request_error(Exception(e))))

    def _fill_table(self, items: list[dict]):
        self.table.setRowCount(len(items))
        for row, question in enumerate(items):
            values = [
                str(question.get("Id", "")),
                str(question.get("Name", "")),
                str(question.get("ParentThemeId", "")),
                str(question.get("DifficultyId", "")),
                "Да" if question.get("IsPrivate") else "Нет",
                "Да" if question.get("IsDeactivated") else "Нет",
                str(question.get("UpdatedAt", ""))[:19],
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))

    def _open_from_table(self, row: int, _col: int):
        if row < 0 or row >= len(self._last_items):
            return
        question_id = self._last_items[row].get("Id")
        if not isinstance(question_id, int):
            self._error("В выбранной строке нет корректного ID")
            return
        self._load_question(question_id)

    def _load_question(self, question_id: int):
        token = self._token()
        self._set_status(f"Загрузка задачи #{question_id}...")

        def _done(question):
            self._current_question = question
            self._show_question(question)
            self._set_status(f"Задача #{question_id} загружена")

        _run(
            lambda: get_question_by_id(question_id, token),
            on_result=_done,
            on_error=lambda e: self._error(_friendly_request_error(Exception(e))),
        )

    def _create_draft(self):
        try:
            token = self._token()
            name = self.f_new_name.text().strip() or "Новая задача"
            theme_id = _to_optional_int(self.f_theme.text())
            if theme_id is None:
                raise ValueError("Для создания нужен ID темы")
            difficulty_id = _to_optional_int(self.f_diff.text()) or 20
            source_id = _to_optional_int(self.f_new_source.text())
        except Exception as exc:
            self._error(f"Ошибка в параметрах создания: {exc}")
            return

        self._set_status("Создание черновика...")

        def _done(result: dict):
            question_id = result.get("Id")
            if not isinstance(question_id, int):
                self._error("Сервер вернул некорректный Id новой задачи")
                return
            self._set_status(f"Черновик создан: #{question_id}")
            self._load_question(question_id)
            self._search()

        _run(
            lambda: create_question_draft(
                token,
                name=name,
                theme_id=theme_id,
                difficulty_id=difficulty_id,
                source_id=source_id,
                answer_text="",
                answer_type_id=1,
                input_type=1,
            ),
            on_result=_done,
            on_error=lambda e: self._error(_friendly_request_error(Exception(e))),
        )

    def _reload_current(self):
        if not self._current_question:
            self._error("Задача не загружена")
            return
        question_id = self._current_question.get("Id")
        if not isinstance(question_id, int):
            self._error("Некорректный ID текущей задачи")
            return
        self._load_question(question_id)

    def _show_question(self, question: dict):
        self.current_label.setText(f"Задача: #{question.get('Id', '?')} — {question.get('Name', '')}")
        self.e_name.setText(str(question.get("Name", "")))
        self.e_parent_theme.setText(str(question.get("ParentThemeId", "")))
        self.e_difficulty.setText(str(question.get("DifficultyId", "")))
        self.e_source.setText(str(question.get("SourceId", "")))
        self.e_sort_order.setText(str(question.get("SortOrder", 0)))
        self.e_lesson_time.setText(str(question.get("LessonTimeCode", 0)))
        self.e_themes.setText(",".join(str(x) for x in (question.get("Themes") or [])))
        self.e_tags.setText(",".join(str(x) for x in (question.get("Tags") or [])))
        self.e_private.setChecked(bool(question.get("IsPrivate")))
        self.e_deactivated.setChecked(bool(question.get("IsDeactivated")))

        answer = question.get("Answer")
        answer_text = answer.get("text", "") if isinstance(answer, dict) else ""
        self.answer_text_box.setPlainText(answer_text)

        answer_type = int(question.get("AnswerTypeId", 1) or 1)
        input_type = int(question.get("InputType", 1) or 1)
        for index in range(self.e_answer_type.count()):
            at, it = self.e_answer_type.itemData(index)
            if at == answer_type:
                self.e_answer_type.setCurrentIndex(index)
                if it != input_type:
                    self.e_input_type.setText(str(input_type))
                break
        else:
            self.e_answer_type.addItem(f"{answer_type} — Пользовательский тип", (answer_type, input_type))
            self.e_answer_type.setCurrentIndex(self.e_answer_type.count() - 1)

        answer_property = question.get("AnswerProperty")
        if isinstance(answer_property, dict):
            self.e_ap_length.setText(str(answer_property.get("length", "")))
            self.e_ap_height.setText(str(answer_property.get("height", "")))
            self.tbl_cols.setValue(max(1, int(answer_property.get("length", 1) or 1)))
            self.tbl_rows.setValue(max(1, int(answer_property.get("height", 1) or 1)))
            self._answer_text_to_table()
        else:
            self.e_ap_length.setText("")
            self.e_ap_height.setText("")

        wrong = question.get("WrongAnswer")
        wrong_text = wrong.get("String", "") if isinstance(wrong, dict) else ""
        self.e_wrong_answers.setPlainText(wrong_text)
        self.e_answer_needs_file.setChecked(bool(question.get("AnswerNeedsAttachment")))
        self.e_answer_is_proof.setChecked(bool(question.get("AnswerIsProof")))

        faq = question.get("Faq") or []
        self.e_faq_json.setPlainText(json.dumps(faq, ensure_ascii=False, indent=2))

        related = question.get("RelatedQuestions") or []
        related_ids: list[str] = []
        if isinstance(related, list):
            for item in related:
                if isinstance(item, dict) and isinstance(item.get("Id"), int):
                    related_ids.append(str(item["Id"]))
        self.e_related.setText(",".join(related_ids))

        self.raw_json.setPlainText(json.dumps(question, ensure_ascii=False, indent=2))

    def _on_answer_type_changed(self):
        answer_type, input_type = self.e_answer_type.currentData()
        self.e_input_type.setText(str(input_type))
        is_table = int(input_type) == 3
        self.e_ap_length.setEnabled(is_table)
        self.e_ap_height.setEnabled(is_table)
        self.tbl_cols.setEnabled(is_table)
        self.tbl_rows.setEnabled(is_table)
        self.btn_resize_table.setEnabled(is_table)
        self.btn_text_to_table.setEnabled(is_table)
        self.btn_table_to_text.setEnabled(is_table)

    def _refresh_raw_json_from_form(self):
        try:
            payload = self._build_payload_from_form()
            self.raw_json.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2))
            self._set_status("JSON обновлён из формы")
        except Exception as exc:
            self._error(f"Не удалось собрать JSON: {exc}")

    def _apply_raw_json_to_form(self):
        try:
            obj = json.loads(self.raw_json.toPlainText())
            if not isinstance(obj, dict):
                raise ValueError("Ожидался JSON-объект задачи")
            self._current_question = obj
            self._show_question(obj)
            self._set_status("JSON применён к форме")
        except Exception as exc:
            self._error(f"Не удалось применить JSON: {exc}")

    def _save_current(self):
        if not self._current_question:
            self._error("Задача не загружена")
            return

        try:
            token = self._token()
            payload = self._build_payload_from_form()
            related_ids = _parse_id_list(self.e_related.text())
        except Exception as exc:
            self._error(f"Ошибка валидации перед сохранением: {exc}")
            return

        self._set_status("Сохраняю задачу...")

        def _do():
            warning = None
            update_question(payload, token)
            try:
                update_related_questions(int(payload["Id"]), related_ids, token)
            except Exception as rel_exc:
                warning = str(rel_exc)
            return int(payload["Id"]), warning

        def _done(result: tuple[int, str | None]):
            question_id, warning = result
            if warning:
                self._set_status(
                    f"Задача #{question_id} сохранена, но связи не обновились: {warning[:120]}"
                )
            else:
                self._set_status(f"Задача #{question_id} сохранена")
            self._load_question(question_id)

        _run(_do, on_result=_done, on_error=lambda e: self._error(_friendly_request_error(Exception(e))))

    def _build_payload_from_form(self) -> dict:
        faq_raw = self.e_faq_json.toPlainText().strip() or "[]"
        faq_json = json.loads(faq_raw)
        if not isinstance(faq_json, list):
            raise ValueError("Faq должен быть JSON-массивом")

        faq: list[list[str]] = []
        for item in faq_json:
            if isinstance(item, str):
                faq.append([item])
            elif isinstance(item, list):
                faq.append([str(x) for x in item if str(x).strip()])
            else:
                raise ValueError("Каждая подсказка должна быть строкой или массивом строк")

        answer_type, input_type = self.e_answer_type.currentData()
        if int(input_type) == 3:
            self._answer_table_to_text()

        answer_property: dict = {}
        if int(input_type) == 3:
            length = int((self.e_ap_length.text().strip() or "0"))
            height = int((self.e_ap_height.text().strip() or "0"))
            answer_property = {"length": length, "height": height}

        wrong_text = self.e_wrong_answers.toPlainText().strip()

        question = patch_question_from_form(
            self._current_question,
            name=self.e_name.text().strip(),
            parent_theme_id=_to_optional_int(self.e_parent_theme.text()),
            difficulty_id=_to_optional_int(self.e_difficulty.text()),
            source_id=_to_optional_int(self.e_source.text()),
            sort_order=int(self.e_sort_order.text().strip() or "0"),
            lesson_time_code=int(self.e_lesson_time.text().strip() or "0"),
            answer_text=self.answer_text_box.toPlainText(),
            is_private=self.e_private.isChecked(),
            is_deactivated=self.e_deactivated.isChecked(),
            themes=_parse_id_list(self.e_themes.text()),
            tags=_parse_id_list(self.e_tags.text()),
            faq=faq,
        )

        question["AnswerTypeId"] = int(answer_type)
        question["InputType"] = int(input_type)
        question["AnswerProperty"] = answer_property
        question["AnswerNeedsAttachment"] = self.e_answer_needs_file.isChecked()
        question["AnswerIsProof"] = self.e_answer_is_proof.isChecked()
        question["WrongAnswer"] = {"String": wrong_text, "Valid": bool(wrong_text)}
        question["FaqText"] = question.get("FaqText", "")
        return question

    def _load_reference_data(self):
        token = self._token()
        self._set_status("Загрузка справочников...")

        def _do():
            themes = list_themes(token)
            tags = list_tags(token)
            difficulties = list_difficulties(token)
            return len(themes), len(tags), len(difficulties)

        def _done(stats: tuple[int, int, int]):
            themes_count, tags_count, diff_count = stats
            self._set_status(
                f"Справочники загружены: темы={themes_count}, теги={tags_count}, сложности={diff_count}"
            )

        _run(_do, on_result=_done, on_error=lambda e: self._error(_friendly_request_error(Exception(e))))

    def _open_hints_window(self):
        if self._hints_window is None:
            self._hints_window = HintsApp()
        self._hints_window.show()
        self._hints_window.raise_()
        self._hints_window.activateWindow()

    def _token(self) -> str:
        token = self.token_edit.text().strip()
        if not token:
            raise ValueError("Нужен JWT токен")
        return token

    def _set_status(self, text: str):
        self._status.setText(text)

    def _error(self, text: str):
        self._set_status(text)
        QMessageBox.critical(self, "Ошибка", text)

    def _save_settings(self):
        data = {"token": self.token_edit.text().strip()}
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
            self._set_status("Настройки сохранены")
        except Exception as exc:
            self._error(f"Не удалось сохранить настройки: {exc}")

    def _load_settings(self):
        token = os.getenv("SHKOLKOVO_TOKEN", "")
        if token:
            self.token_edit.setText(token)
            return
        if not os.path.exists(SETTINGS_FILE):
            return
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as file:
                data = json.load(file)
            if data.get("token"):
                self.token_edit.setText(data["token"])
        except Exception:
            pass

