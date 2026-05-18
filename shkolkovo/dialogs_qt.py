"""dialogs_qt.py — все диалоговые окна на PyQt6."""
import csv
import json
import os

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QScrollArea, QWidget, QFrame,
    QTreeWidget, QTreeWidgetItem, QFileDialog, QMessageBox,
    QDialogButtonBox, QSpinBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from .config import (CARD, BORDER, ACCENT, ACCENT2, TEXT, MUTED,
                     SUCCESS, DANGER, HINT_ACCENTS, SURFACE)


def _label(text: str, bold: bool = False, muted: bool = False,
           size: int = 13) -> QLabel:
    lbl = QLabel(text)
    f = lbl.font()
    f.setPointSize(size)
    if bold:
        f.setBold(True)
    lbl.setFont(f)
    if muted:
        lbl.setProperty("muted", "true")
    return lbl


def _btn(text: str, prop: str | None = None,
         width: int | None = None) -> QPushButton:
    b = QPushButton(text)
    if prop:
        b.setProperty(prop, "true")
    if width:
        b.setFixedWidth(width)
    return b


# ── SettingsDialog ─────────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    saved = pyqtSignal(dict)

    def __init__(self, parent, current: dict):
        super().__init__(parent)
        self.setWindowTitle("⚙ Настройки подключения")
        self.setMinimumWidth(520)
        self.setModal(True)

        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(20, 20, 20, 20)

        fields = [
            ("JWT токен:", "token", True),
            ("Groq API Key:", "api_key", True),
            ("Прокси (http://host:port):", "proxy", False),
        ]
        self._entries: dict[str, QLineEdit] = {}
        for label, key, secret in fields:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setFixedWidth(200)
            row.addWidget(lbl)
            edit = QLineEdit()
            if secret:
                edit.setEchoMode(QLineEdit.EchoMode.Password)
            if current.get(key):
                edit.setText(current[key])
            row.addWidget(edit)
            lay.addLayout(row)
            self._entries[key] = edit

        ssl_row = QHBoxLayout()
        self._ssl_cb = QCheckBox("Проверка SSL-сертификата")
        self._ssl_cb.setChecked(current.get("verify_ssl", True))
        ssl_row.addWidget(self._ssl_cb)
        note = QLabel("← снимите при ошибках VPN/прокси")
        note.setProperty("muted", "true")
        ssl_row.addWidget(note)
        ssl_row.addStretch()
        lay.addLayout(ssl_row)

        lay.addSpacing(8)
        btns = QHBoxLayout()
        save = _btn("💾 Сохранить", "accent", 130)
        save.clicked.connect(self._save)
        cancel = _btn("Отмена", width=90)
        cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(save)
        btns.addWidget(cancel)
        lay.addLayout(btns)

    def _save(self):
        result = {k: e.text().strip() for k, e in self._entries.items()}
        result["verify_ssl"] = self._ssl_cb.isChecked()
        self.saved.emit(result)
        self.accept()


# ── ThemeQueueDialog ───────────────────────────────────────────────────────────

class ThemeQueueDialog(QDialog):
    queue_ready = pyqtSignal(list)   # list of str IDs

    def __init__(self, parent, on_load_fn):
        super().__init__(parent)
        self.setWindowTitle("📂 Загрузить очередь из темы")
        self.setMinimumWidth(440)
        self.setModal(True)
        self._on_load_fn = on_load_fn

        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(20, 20, 20, 20)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("ID родительской темы:"))
        self._theme_edit = QLineEdit()
        self._theme_edit.setPlaceholderText("например, 42")
        row1.addWidget(self._theme_edit)
        lay.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Макс. задач:"))
        self._limit = QSpinBox()
        self._limit.setRange(1, 1000)
        self._limit.setValue(200)
        row2.addWidget(self._limit)
        row2.addStretch()
        lay.addLayout(row2)

        self._info = QLabel("")
        self._info.setProperty("muted", "true")
        self._info.setWordWrap(True)
        lay.addWidget(self._info)

        btns = QHBoxLayout()
        self._load_btn = _btn("📥 Загрузить", "accent", 140)
        self._load_btn.clicked.connect(self._do_load)
        cancel = _btn("Отмена", width=90)
        cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(self._load_btn)
        btns.addWidget(cancel)
        lay.addLayout(btns)

    def _do_load(self):
        tid = self._theme_edit.text().strip()
        if not tid.isdigit():
            self._info.setText("❌ Введите числовой ID темы")
            return
        self._load_btn.setEnabled(False)
        self._load_btn.setText("⏳ Загружаю…")
        self._info.setText("Отправляю запрос…")
        self._on_load_fn(int(tid), self._limit.value(), self._on_result)

    def _on_result(self, questions: list, error: str = ""):
        self._load_btn.setEnabled(True)
        self._load_btn.setText("📥 Загрузить")
        if error:
            self._info.setText(f"❌ {error[:120]}")
            return
        if not questions:
            self._info.setText("✅ Все задачи темы уже имеют подсказки!")
            return
        ids = [str(q["Id"]) for q in questions if q.get("Id")]
        self._info.setText(f"✅ Найдено {len(ids)} задач без подсказок")
        self.queue_ready.emit(ids)
        self.accept()


# ── LogDialog ──────────────────────────────────────────────────────────────────

class LogDialog(QDialog):
    def __init__(self, parent, log_entries: list):
        super().__init__(parent)
        self.setWindowTitle("📋 Лог обработки")
        self.resize(780, 520)
        self.setModal(True)
        self._entries = log_entries

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        # Header stats
        total = len(log_entries)
        ok = sum(1 for e in log_entries if e.get("ok"))
        hdr = QLabel(f"Всего задач: {total}   ✅ {ok}   ❌ {total - ok}")
        f = hdr.font(); f.setBold(True); f.setPointSize(13); hdr.setFont(f)
        lay.addWidget(hdr)

        # Table
        tree = QTreeWidget()
        tree.setColumnCount(6)
        tree.setHeaderLabels(["", "ID", "Название", "Подск.", "Время", "Длит."])
        tree.setAlternatingRowColors(True)
        tree.setRootIsDecorated(False)
        tree.header().setStretchLastSection(False)
        tree.setColumnWidth(0, 30)
        tree.setColumnWidth(1, 75)
        tree.setColumnWidth(2, 350)
        tree.setColumnWidth(3, 55)
        tree.setColumnWidth(4, 80)
        tree.setColumnWidth(5, 65)

        for entry in reversed(log_entries):
            ok_flag = entry.get("ok")
            dur = entry.get("duration_sec", 0) or 0
            dur_str = f"{int(dur//60)}м{int(dur%60)}с" if dur else "—"
            item = QTreeWidgetItem([
                "✅" if ok_flag else "❌",
                str(entry.get("id", "")),
                str(entry.get("name", ""))[:60],
                str(entry.get("hints", "")),
                str(entry.get("ts", ""))[:16],
                dur_str,
            ])
            tree.addTopLevelItem(item)

        lay.addWidget(tree)

        btns = QHBoxLayout()
        exp = _btn("💾 Экспорт CSV", "accent", 140)
        exp.clicked.connect(self._export)
        clr = _btn("🗑 Очистить", "danger", 110)
        clr.clicked.connect(self._clear)
        close = _btn("Закрыть", width=90)
        close.clicked.connect(self.accept)
        btns.addWidget(exp)
        btns.addWidget(clr)
        btns.addStretch()
        btns.addWidget(close)
        lay.addLayout(btns)

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить лог", "shkolkovo_log.csv",
            "CSV файлы (*.csv);;Все файлы (*.*)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["date","ts","id","name","hints","ok"])
            w.writeheader()
            w.writerows(self._entries)
        QMessageBox.information(self, "Экспорт", f"Сохранено:\n{path}")

    def _clear(self):
        if QMessageBox.question(
            self, "Очистить", "Удалить весь лог за сегодня?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self._entries.clear()
            self.accept()


# ── HintPreviewDialog ──────────────────────────────────────────────────────────

class HintPreviewDialog(QDialog):
    def __init__(self, parent, hints: list, question_name: str = ""):
        super().__init__(parent)
        self.setWindowTitle(f"👁 Предпросмотр — {question_name or 'Подсказки'}")
        self.resize(640, 560)
        self.setModal(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        ctr_lay = QVBoxLayout(container)
        ctr_lay.setSpacing(10)
        scroll.setWidget(container)
        lay.addWidget(scroll)

        for idx, hint in enumerate(hints):
            color = HINT_ACCENTS[idx % len(HINT_ACCENTS)]
            parts = hint if isinstance(hint, list) else [hint]

            card = QFrame()
            card.setProperty("card", "true")
            card_lay = QVBoxLayout(card)
            card_lay.setContentsMargins(12, 8, 12, 8)

            # colored stripe
            stripe = QFrame()
            stripe.setFixedHeight(3)
            stripe.setStyleSheet(f"background:{color}; border:none;")
            card_lay.addWidget(stripe)

            for pi, part in enumerate(parts):
                prefix = "→ " if pi > 0 else f"#{idx+1}  "
                lbl = QLabel(f"{prefix}{part}")
                lbl.setWordWrap(True)
                f = lbl.font()
                f.setBold(pi == 0)
                lbl.setFont(f)
                card_lay.addWidget(lbl)

            ctr_lay.addWidget(card)

        ctr_lay.addStretch()

        btns = QHBoxLayout()
        copy_json = _btn("📋 Копировать JSON", width=160)
        copy_json.clicked.connect(lambda: self._copy_json(hints))
        close = _btn("Закрыть", width=90)
        close.clicked.connect(self.accept)
        btns.addWidget(copy_json)
        btns.addStretch()
        btns.addWidget(close)
        lay.addLayout(btns)

    def _copy_json(self, hints):
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(
            json.dumps(hints, ensure_ascii=False, indent=2))


# ── InputDialog ────────────────────────────────────────────────────────────────

def ask_text(parent, title: str, prompt: str) -> str | None:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setMinimumWidth(340)
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel(prompt))
    edit = QLineEdit()
    lay.addWidget(edit)
    btns = QHBoxLayout()
    ok = _btn("OK", "accent", 80)
    ok.clicked.connect(dlg.accept)
    cancel = _btn("Отмена", width=80)
    cancel.clicked.connect(dlg.reject)
    btns.addStretch()
    btns.addWidget(ok)
    btns.addWidget(cancel)
    lay.addLayout(btns)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        return edit.text().strip() or None
    return None
