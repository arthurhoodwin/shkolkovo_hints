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
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .api import _friendly_request_error
from .app_qt import _run
from .task_client_api import (
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


def _to_optional_int(text: str) -> int | None:
    value = text.strip()
    if not value:
        return None
    return int(value)


def _parse_id_list(text: str) -> list[int]:
    raw = text.replace(";", ",").replace("\n", ",")
    items: list[int] = []
    for part in raw.split(","):
        p = part.strip()
        if not p:
            continue
        items.append(int(p))
    return items


class FullClientApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Shkolkovo Full Client (MVP)")
        self.resize(1540, 920)
        self.setMinimumSize(1240, 760)

        self._current_question: dict | None = None
        self._last_items: list[dict] = []

        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(self._build_topbar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_editor_panel())
        splitter.setSizes([700, 820])
        layout.addWidget(splitter, 1)

        self._status = QLabel("Ready")
        bar = QStatusBar()
        bar.addWidget(self._status)
        self.setStatusBar(bar)

    def _build_topbar(self) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        row.addWidget(QLabel("JWT:"))
        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_edit.setPlaceholderText("eyJ...")
        row.addWidget(self.token_edit, 1)

        self.load_refs_btn = QPushButton("Load Dictionaries")
        self.load_refs_btn.clicked.connect(self._load_reference_data)
        row.addWidget(self.load_refs_btn)

        self.save_settings_btn = QPushButton("Save Settings")
        self.save_settings_btn.clicked.connect(self._save_settings)
        row.addWidget(self.save_settings_btn)
        return box

    def _build_left_panel(self) -> QWidget:
        wrapper = QWidget()
        col = QVBoxLayout(wrapper)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(8)

        filters = QGroupBox("Question Search")
        grid = QGridLayout(filters)

        self.f_qid = QLineEdit()
        self.f_qid.setPlaceholderText("Question ID")
        self.f_theme = QLineEdit()
        self.f_theme.setPlaceholderText("Parent Theme ID")
        self.f_diff = QLineEdit()
        self.f_diff.setPlaceholderText("Difficulty ID")

        self.f_private = QComboBox()
        self.f_private.addItems(["Any privacy", "Public only", "Private only"])

        self.f_deactivated = QComboBox()
        self.f_deactivated.addItems(["Any status", "Active only", "Deactivated only"])

        self.f_page = QLineEdit("1")
        self.f_per_page = QLineEdit("50")

        grid.addWidget(QLabel("Question"), 0, 0)
        grid.addWidget(self.f_qid, 0, 1)
        grid.addWidget(QLabel("Theme"), 0, 2)
        grid.addWidget(self.f_theme, 0, 3)
        grid.addWidget(QLabel("Difficulty"), 1, 0)
        grid.addWidget(self.f_diff, 1, 1)
        grid.addWidget(QLabel("Privacy"), 1, 2)
        grid.addWidget(self.f_private, 1, 3)
        grid.addWidget(QLabel("Status"), 2, 0)
        grid.addWidget(self.f_deactivated, 2, 1)
        grid.addWidget(QLabel("Page"), 2, 2)
        grid.addWidget(self.f_page, 2, 3)
        grid.addWidget(QLabel("Per page"), 3, 0)
        grid.addWidget(self.f_per_page, 3, 1)

        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self._search)
        grid.addWidget(self.search_btn, 3, 3)

        col.addWidget(filters)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Id", "Name", "Theme", "Difficulty", "Private", "Off", "Updated"]
        )
        self.table.cellDoubleClicked.connect(self._open_from_table)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        col.addWidget(self.table, 1)

        return wrapper

    def _build_editor_panel(self) -> QWidget:
        wrapper = QWidget()
        col = QVBoxLayout(wrapper)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(8)

        header = QHBoxLayout()
        self.current_label = QLabel("Question: not loaded")
        header.addWidget(self.current_label)
        header.addStretch()

        self.reload_btn = QPushButton("Reload")
        self.reload_btn.clicked.connect(self._reload_current)
        header.addWidget(self.reload_btn)

        self.save_btn = QPushButton("Save to Platform")
        self.save_btn.clicked.connect(self._save_current)
        header.addWidget(self.save_btn)
        col.addLayout(header)

        form_box = QGroupBox("Question Card")
        form = QFormLayout(form_box)

        self.e_name = QLineEdit()
        self.e_parent_theme = QLineEdit()
        self.e_difficulty = QLineEdit()
        self.e_source = QLineEdit()
        self.e_sort_order = QLineEdit()
        self.e_lesson_time = QLineEdit()
        self.e_themes = QLineEdit()
        self.e_tags = QLineEdit()
        self.e_related = QLineEdit()
        self.e_answer = QPlainTextEdit()
        self.e_answer.setMinimumHeight(90)
        self.e_faq_json = QPlainTextEdit()
        self.e_faq_json.setMinimumHeight(220)

        self.e_private = QCheckBox("Is private")
        self.e_deactivated = QCheckBox("Is deactivated")

        form.addRow("Name", self.e_name)
        form.addRow("ParentThemeId", self.e_parent_theme)
        form.addRow("DifficultyId", self.e_difficulty)
        form.addRow("SourceId", self.e_source)
        form.addRow("SortOrder", self.e_sort_order)
        form.addRow("LessonTimeCode", self.e_lesson_time)
        form.addRow("Themes (id,id,...)", self.e_themes)
        form.addRow("Tags (id,id,...)", self.e_tags)
        form.addRow("Related questions (id,id,...)", self.e_related)
        form.addRow(self.e_private)
        form.addRow(self.e_deactivated)
        form.addRow("Answer text", self.e_answer)
        form.addRow("Faq JSON (list of string lists)", self.e_faq_json)
        col.addWidget(form_box, 1)
        return wrapper

    def _search(self):
        try:
            token = self._token()
            question_id = _to_optional_int(self.f_qid.text())
            theme_id = _to_optional_int(self.f_theme.text())
            diff_id = _to_optional_int(self.f_diff.text())
            page = int(self.f_page.text().strip() or "1")
            per_page = int(self.f_per_page.text().strip() or "50")
        except Exception as exc:
            self._error(f"Invalid filter values: {exc}")
            return

        privacy = self.f_private.currentIndex()
        is_private = None if privacy == 0 else privacy == 2
        deactivated = self.f_deactivated.currentIndex()
        is_deactivated = None if deactivated == 0 else deactivated == 2

        self._set_status("Loading questions...")

        def _do():
            return list_questions(
                token,
                page=page,
                per_page=per_page,
                question_id=question_id,
                parent_theme_id=theme_id,
                difficulty_id=diff_id,
                is_private=is_private,
                is_deactivated=is_deactivated,
            )

        def _done(data):
            items, _payload = data
            self._last_items = items
            self._fill_table(items)
            self._set_status(f"Loaded {len(items)} questions")

        _run(_do, on_result=_done, on_error=lambda e: self._error(_friendly_request_error(Exception(e))))

    def _fill_table(self, items: list[dict]):
        self.table.setRowCount(len(items))
        for row, q in enumerate(items):
            values = [
                str(q.get("Id", "")),
                str(q.get("Name", "")),
                str(q.get("ParentThemeId", "")),
                str(q.get("DifficultyId", "")),
                "yes" if q.get("IsPrivate") else "no",
                "yes" if q.get("IsDeactivated") else "no",
                str(q.get("UpdatedAt", ""))[:19],
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))

    def _open_from_table(self, row: int, _col: int):
        if row < 0 or row >= len(self._last_items):
            return
        qid = self._last_items[row].get("Id")
        if not isinstance(qid, int):
            self._error("Selected row has no numeric question id")
            return
        self._load_question(qid)

    def _load_question(self, question_id: int):
        token = self._token()
        self._set_status(f"Loading question #{question_id}...")

        def _done(question):
            self._current_question = question
            self._show_question(question)
            self._set_status(f"Question #{question_id} loaded")

        _run(
            lambda: get_question_by_id(question_id, token),
            on_result=_done,
            on_error=lambda e: self._error(_friendly_request_error(Exception(e))),
        )

    def _reload_current(self):
        if not self._current_question:
            self._error("No question loaded")
            return
        qid = self._current_question.get("Id")
        if not isinstance(qid, int):
            self._error("Current question has invalid Id")
            return
        self._load_question(qid)

    def _show_question(self, q: dict):
        self.current_label.setText(f"Question #{q.get('Id', '?')}")
        self.e_name.setText(str(q.get("Name", "")))
        self.e_parent_theme.setText(str(q.get("ParentThemeId", "")))
        self.e_difficulty.setText(str(q.get("DifficultyId", "")))
        self.e_source.setText(str(q.get("SourceId", "")))
        self.e_sort_order.setText(str(q.get("SortOrder", 0)))
        self.e_lesson_time.setText(str(q.get("LessonTimeCode", 0)))
        self.e_themes.setText(",".join(str(x) for x in (q.get("Themes") or [])))
        self.e_tags.setText(",".join(str(x) for x in (q.get("Tags") or [])))

        related = q.get("RelatedQuestions") or []
        related_ids: list[str] = []
        if isinstance(related, list):
            for rel in related:
                if isinstance(rel, dict) and isinstance(rel.get("Id"), int):
                    related_ids.append(str(rel["Id"]))
        self.e_related.setText(",".join(related_ids))

        self.e_private.setChecked(bool(q.get("IsPrivate")))
        self.e_deactivated.setChecked(bool(q.get("IsDeactivated")))

        answer = q.get("Answer")
        answer_text = answer.get("text", "") if isinstance(answer, dict) else ""
        self.e_answer.setPlainText(answer_text)

        faq = q.get("Faq") or []
        self.e_faq_json.setPlainText(json.dumps(faq, ensure_ascii=False, indent=2))

    def _save_current(self):
        if not self._current_question:
            self._error("No question loaded")
            return

        try:
            faq_raw = self.e_faq_json.toPlainText().strip() or "[]"
            faq = json.loads(faq_raw)
            if not isinstance(faq, list):
                raise ValueError("Faq must be a JSON list")
            normalized_faq: list[list[str]] = []
            for hint in faq:
                if isinstance(hint, str):
                    normalized_faq.append([hint])
                elif isinstance(hint, list):
                    normalized_faq.append([str(part) for part in hint if str(part).strip()])
                else:
                    raise ValueError("Each hint must be string or list of strings")

            patch = patch_question_from_form(
                self._current_question,
                name=self.e_name.text().strip(),
                parent_theme_id=_to_optional_int(self.e_parent_theme.text()),
                difficulty_id=_to_optional_int(self.e_difficulty.text()),
                source_id=_to_optional_int(self.e_source.text()),
                sort_order=int(self.e_sort_order.text().strip() or "0"),
                lesson_time_code=int(self.e_lesson_time.text().strip() or "0"),
                answer_text=self.e_answer.toPlainText(),
                is_private=self.e_private.isChecked(),
                is_deactivated=self.e_deactivated.isChecked(),
                themes=_parse_id_list(self.e_themes.text()),
                tags=_parse_id_list(self.e_tags.text()),
                faq=normalized_faq,
            )
            related_ids = _parse_id_list(self.e_related.text())
            token = self._token()
        except Exception as exc:
            self._error(f"Validation error: {exc}")
            return

        self._set_status("Saving question...")

        def _do():
            update_question(patch, token)
            update_related_questions(int(patch["Id"]), related_ids, token)
            return int(patch["Id"])

        def _done(qid: int):
            self._set_status(f"Question #{qid} saved")
            self._load_question(qid)

        _run(_do, on_result=_done, on_error=lambda e: self._error(_friendly_request_error(Exception(e))))

    def _load_reference_data(self):
        token = self._token()
        self._set_status("Loading dictionaries...")

        def _do():
            themes = list_themes(token)
            tags = list_tags(token)
            difficulties = list_difficulties(token)
            return len(themes), len(tags), len(difficulties)

        def _done(stats: tuple[int, int, int]):
            t, g, d = stats
            self._set_status(f"Dictionaries loaded: themes={t}, tags={g}, difficulties={d}")

        _run(_do, on_result=_done, on_error=lambda e: self._error(_friendly_request_error(Exception(e))))

    def _token(self) -> str:
        token = self.token_edit.text().strip()
        if not token:
            raise ValueError("JWT token is required")
        return token

    def _set_status(self, text: str):
        self._status.setText(text)

    def _error(self, text: str):
        self._set_status(text)
        QMessageBox.critical(self, "Error", text)

    def _save_settings(self):
        data = {"token": self.token_edit.text().strip()}
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._set_status("Settings saved")
        except Exception as exc:
            self._error(f"Failed to save settings: {exc}")

    def _load_settings(self):
        token = os.getenv("SHKOLKOVO_TOKEN", "")
        if token:
            self.token_edit.setText(token)
            return
        if not os.path.exists(SETTINGS_FILE):
            return
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("token"):
                self.token_edit.setText(data["token"])
        except Exception:
            pass

