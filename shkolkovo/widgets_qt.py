"""widgets_qt.py — HintCard и HintsEditor на PyQt6."""
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QScrollArea, QWidget, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from .config import HINT_ACCENTS, BORDER, MUTED, CARD, TEXT


# ── Helpers ───────────────────────────────────────────────────────────────────

def _btn(text: str, tooltip: str = "", width: int | None = None,
         prop: str | None = None) -> QPushButton:
    b = QPushButton(text)
    if tooltip:
        b.setToolTip(tooltip)
    if width:
        b.setFixedWidth(width)
    if prop:
        b.setProperty(prop, "true")
        b.style().unpolish(b)
        b.style().polish(b)
    return b


# ── HintCard ──────────────────────────────────────────────────────────────────

class HintCard(QFrame):
    """Редактируемая карточка одной подсказки."""

    delete_requested  = pyqtSignal(object)   # self
    move_up_requested = pyqtSignal(object)
    move_dn_requested = pyqtSignal(object)
    regen_requested   = pyqtSignal(object)
    changed           = pyqtSignal()

    def __init__(self, hint_data: list, index: int,
                 color: str, show_regen: bool = True):
        super().__init__()
        self.setProperty("card", "true")
        self._color = color
        self._collapsed = False
        self._step_rows: list[QWidget] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Colored top stripe ────────────────────────────────────────────────
        stripe = QFrame()
        stripe.setFixedHeight(3)
        stripe.setStyleSheet(f"background:{color}; border:none; border-radius:0;")
        root.addWidget(stripe)

        # ── Header row ────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(10, 6, 6, 4)
        hdr_lay.setSpacing(6)

        num = QLabel(str(index))
        num.setFixedSize(26, 26)
        num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num.setStyleSheet(
            f"background:{color}; color:white; border-radius:13px;"
            f" font-weight:700; font-size:11px;")
        hdr_lay.addWidget(num)
        self._num_label = num

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Название подсказки")
        self.title_edit.setStyleSheet("font-weight:600;")
        if hint_data and hint_data[0]:
            self.title_edit.setText(hint_data[0])
            self.title_edit.setCursorPosition(0)
        self.title_edit.textChanged.connect(self.changed)
        self.title_edit.editingFinished.connect(lambda: self.title_edit.setCursorPosition(0))
        hdr_lay.addWidget(self.title_edit, 1)

        # icon buttons
        for icon, tip, sig in [
            ("▾", "Свернуть/развернуть", None),
            ("↑", "Переместить выше",  self.move_up_requested),
            ("↓", "Переместить ниже",  self.move_dn_requested),
            ("📋","Копировать",         None),
        ]:
            b = QPushButton(icon)
            b.setFixedSize(26, 26)
            b.setToolTip(tip)
            b.setStyleSheet(
                f"QPushButton{{background:transparent;border:none;color:{MUTED};}}"
                f"QPushButton:hover{{color:{TEXT};}}")
            if sig is not None:
                b.clicked.connect(lambda _checked, s=sig: s.emit(self))
            elif icon == "▾":
                b.clicked.connect(self._toggle_collapse)
                self._collapse_btn = b
            elif icon == "📋":
                b.clicked.connect(self._copy)
            hdr_lay.addWidget(b)

        if show_regen:
            rb = QPushButton("🔄")
            rb.setFixedSize(26, 26)
            rb.setToolTip("Регенерировать эту подсказку")
            rb.setStyleSheet(
                f"QPushButton{{background:transparent;border:none;color:#4da3ff;}}"
                f"QPushButton:hover{{color:#7ec8ff;}}")
            rb.clicked.connect(lambda: self.regen_requested.emit(self))
            hdr_lay.addWidget(rb)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(26, 26)
        del_btn.setToolTip("Удалить подсказку")
        del_btn.setStyleSheet(
            "QPushButton{background:transparent;border:none;color:#ef4444;}"
            "QPushButton:hover{color:#ff6b6b;}")
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self))
        hdr_lay.addWidget(del_btn)

        root.addWidget(hdr)

        # ── Steps area ────────────────────────────────────────────────────────
        self._body = QWidget()
        body_lay = QVBoxLayout(self._body)
        body_lay.setContentsMargins(44, 0, 10, 4)
        body_lay.setSpacing(3)

        self._steps_lay = QVBoxLayout()
        self._steps_lay.setSpacing(3)
        body_lay.addLayout(self._steps_lay)

        steps = hint_data[1:] if len(hint_data) > 1 else [""]
        for s in steps:
            self._add_step(s)

        add_step = QPushButton("＋ шаг")
        add_step.setFixedHeight(22)
        add_step.setStyleSheet(
            f"QPushButton{{background:transparent;border:1px solid {BORDER};"
            f"color:{MUTED};border-radius:4px;font-size:10px;padding:0 6px;}}"
            f"QPushButton:hover{{color:{TEXT};}}")
        add_step.clicked.connect(lambda: self._add_step(""))
        body_lay.addWidget(add_step, 0, Qt.AlignmentFlag.AlignLeft)

        root.addWidget(self._body)

    def _add_step(self, text: str):
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        arrow = QLabel("→")
        arrow.setStyleSheet(f"color:{self._color}; font-size:11px;")
        arrow.setFixedWidth(16)
        lay.addWidget(arrow)

        edit = QLineEdit()
        edit.setPlaceholderText(f"Шаг {self._steps_lay.count() + 1}…")
        edit.setFixedHeight(26)
        if text:
            edit.setText(text)
            edit.setCursorPosition(0)
        edit.editingFinished.connect(lambda e=edit: e.setCursorPosition(0))
        edit.textChanged.connect(self.changed)
        lay.addWidget(edit, 1)

        rm = QPushButton("−")
        rm.setFixedSize(22, 22)
        rm.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;color:{MUTED};font-size:14px;}}"
            f"QPushButton:hover{{color:#ef4444;}}")
        rm.clicked.connect(lambda: self._remove_step(row))
        lay.addWidget(rm)

        self._steps_lay.addWidget(row)
        self._step_rows.append(row)

    def _remove_step(self, row: QWidget):
        if row in self._step_rows:
            self._step_rows.remove(row)
        row.deleteLater()
        self.changed.emit()

    def _toggle_collapse(self):
        self._collapsed = not self._collapsed
        self._body.setVisible(not self._collapsed)
        self._collapse_btn.setText("▸" if self._collapsed else "▾")

    def _copy(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(" → ".join(self.get_hint()))

    def get_hint(self) -> list:
        title = self.title_edit.text().strip()
        steps = []
        for row in self._step_rows:
            edit = row.findChild(QLineEdit)
            if edit:
                t = edit.text().strip()
                if t:
                    steps.append(t)
        result = ([title] if title else []) + steps
        return result or ["Новая подсказка", ""]

    def set_index(self, idx: int):
        self._num_label.setText(str(idx))

    def set_hint(self, hint_data: list):
        self.title_edit.blockSignals(True)
        self.title_edit.setText(hint_data[0] if hint_data else "")
        self.title_edit.setCursorPosition(0)
        self.title_edit.blockSignals(False)
        # clear step rows immediately (not deleteLater)
        for row in list(self._step_rows):
            self._steps_lay.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        self._step_rows.clear()
        steps = hint_data[1:] if len(hint_data) > 1 else [""]
        for s in steps:
            self._add_step(s)


# ── HintsEditor ───────────────────────────────────────────────────────────────

class HintsEditor(QScrollArea):
    """Прокручиваемый список карточек HintCard."""

    changed       = pyqtSignal()
    regen_one     = pyqtSignal(int)   # index

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._lay = QVBoxLayout(self._container)
        self._lay.setContentsMargins(4, 4, 4, 4)
        self._lay.setSpacing(8)
        self._lay.addStretch(1)  # spacer at bottom
        self.setWidget(self._container)

        self._cards: list[HintCard] = []

    # ── Public API ──────────────────────────────────────────────────────────

    def load_hints(self, hints: list):
        self._clear_cards()
        for h in hints:
            if isinstance(h, str):
                h = [h]
            self._append_card(list(h))
        self.changed.emit()

    def add_empty_hint(self):
        self._append_card(["Новая подсказка", ""])
        self.changed.emit()

    def get_hints(self) -> list:
        return [c.get_hint() for c in self._cards
                if any(p.strip() for p in c.get_hint())]

    def clear(self):
        self._clear_cards()
        self.changed.emit()

    def count(self) -> int:
        return len(self._cards)

    def update_card(self, idx: int, new_hint: list):
        if 0 <= idx < len(self._cards):
            self._cards[idx].set_hint(new_hint)
            self.changed.emit()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _append_card(self, hint_data: list):
        idx = len(self._cards)
        color = HINT_ACCENTS[idx % len(HINT_ACCENTS)]
        card = HintCard(hint_data, idx + 1, color, show_regen=True)
        card.delete_requested.connect(self._on_delete)
        card.move_up_requested.connect(self._on_move_up)
        card.move_dn_requested.connect(self._on_move_dn)
        card.regen_requested.connect(self._on_regen)
        card.changed.connect(self.changed)
        # insert before the stretch
        self._lay.insertWidget(self._lay.count() - 1, card)
        self._cards.append(card)

    def _clear_cards(self):
        for card in self._cards:
            card.setParent(None)   # immediately removes from layout & parent
        self._cards.clear()

    def _renumber(self):
        for i, card in enumerate(self._cards):
            card.set_index(i + 1)

    def _on_delete(self, card: HintCard):
        if card not in self._cards:
            return
        idx = self._cards.index(card)
        self._cards.pop(idx)
        card.setParent(None)   # immediately removes from layout
        self._renumber()
        self.changed.emit()

    def _on_move_up(self, card: HintCard):
        idx = self._cards.index(card)
        if idx == 0:
            return
        self._swap(idx, idx - 1)

    def _on_move_dn(self, card: HintCard):
        idx = self._cards.index(card)
        if idx >= len(self._cards) - 1:
            return
        self._swap(idx, idx + 1)

    def _swap(self, a: int, b: int):
        # Swap hint *content* between cards (cards stay in place visually
        # but their data swaps — cleaner than re-parenting widgets).
        ha = self._cards[a].get_hint()
        hb = self._cards[b].get_hint()
        self._cards[a].set_hint(hb)
        self._cards[b].set_hint(ha)
        # Also swap badge numbers so they always match position
        self._cards[a].set_index(a + 1)
        self._cards[b].set_index(b + 1)
        self.changed.emit()

    def _on_regen(self, card: HintCard):
        idx = self._cards.index(card)
        self.regen_one.emit(idx)
