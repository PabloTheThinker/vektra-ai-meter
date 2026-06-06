from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .theme import (
    BG,
    BG_CARD,
    BG_ELEVATED,
    BORDER,
    BORDER_SUBTLE,
    TEXT,
    TEXT_DIM,
    TEXT_MUTED,
    PANEL_WIDTH,
    provider_style,
    usage_color,
    window_title,
)
from .wayland import apply_dropdown_window_flags, show_panel_near_tray

CARET_HEIGHT = 11


def _reset_hint(value: str | None) -> str:
    if not value:
        return ""
    try:
        raw = value.replace("Z", "+00:00")
        resets = datetime.fromisoformat(raw)
        if resets.tzinfo is None:
            resets = resets.replace(tzinfo=timezone.utc)
        delta = resets - datetime.now(timezone.utc)
        minutes = int(delta.total_seconds() // 60)
        if minutes <= 0:
            return "Resets soon"
        if minutes < 60:
            return f"Resets in {minutes}m"
        hours = minutes // 60
        if hours < 48:
            return f"Resets in {hours}h"
        days = hours // 24
        return f"Resets in {days}d"
    except ValueError:
        return ""


def ago_label(iso_value: str | None) -> str:
    if not iso_value:
        return ""
    try:
        raw = iso_value.replace("Z", "+00:00")
        generated = datetime.fromisoformat(raw)
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=timezone.utc)
        seconds = int((datetime.now(timezone.utc) - generated).total_seconds())
        if seconds < 5:
            return "Updated just now"
        if seconds < 60:
            return f"Updated {seconds}s ago"
        if seconds < 3600:
            return f"Updated {seconds // 60}m ago"
        return f"Updated {seconds // 3600}h ago"
    except ValueError:
        return ""


class DropdownCaret(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._offset = 0
        self.setFixedHeight(CARET_HEIGHT)

    def set_offset(self, x: int) -> None:
        self._offset = x
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = max(16, min(self.width() - 16, self._offset))
        half = 8
        base = self.height() - 1

        fill = QColor(BG)
        border = QColor(BORDER)

        left = QPoint(cx - half, base)
        right = QPoint(cx + half, base)
        tip = QPoint(cx, 0)

        painter.setBrush(fill)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygon([left, right, tip]))

        painter.setPen(QPen(border, 1))
        painter.drawLine(left, tip)
        painter.drawLine(tip, right)


class ProviderBadge(QLabel):
    def __init__(self, provider_id: str) -> None:
        style = provider_style(provider_id)
        super().__init__(style["badge"])
        self._accent = style["accent"]
        self.setFixedSize(30, 30)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_style()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            "QLabel {"
            f"  background: {self._accent}22;"
            f"  color: {self._accent};"
            "  border-radius: 9px;"
            "  font-size: 11px;"
            "  font-weight: 700;"
            "  letter-spacing: -0.3px;"
            "}"
        )


class SummaryPill(QLabel):
    def __init__(self, text: str, *, accent: str, percent: float | None = None) -> None:
        super().__init__(text)
        self._accent = accent
        self._percent = percent
        self._apply_style()

    def set_content(self, text: str, *, accent: str, percent: float | None = None) -> None:
        self.setText(text)
        self._accent = accent
        self._percent = percent
        self._apply_style()

    def _apply_style(self) -> None:
        border = usage_color(self._percent) if self._percent is not None else BORDER
        self.setStyleSheet(
            "QLabel {"
            f"  background: {self._accent}18;"
            f"  color: {TEXT};"
            f"  border: 1px solid {border}55;"
            "  border-radius: 999px;"
            "  padding: 5px 11px;"
            "  font-size: 11px;"
            "  font-weight: 600;"
            "}"
        )


class UsageWindowRow(QWidget):
    """CodexBar-style quota row: title + reset, thin bar, used %."""

    def __init__(
        self,
        label: str,
        used_percent: float | None,
        *,
        resets_at: str | None = None,
        used_tokens: str | None = None,
        limit_tokens: str | None = None,
    ) -> None:
        super().__init__()
        self._label_key = label
        self._title = QLabel(window_title(label))
        self._reset_label = QLabel("")
        self._bar = QProgressBar()
        self._pct = QLabel("")
        self._detail = QLabel("")
        self._build(used_percent, resets_at, used_tokens, limit_tokens)

    def _build(
        self,
        used_percent: float | None,
        resets_at: str | None,
        used_tokens: str | None,
        limit_tokens: str | None,
    ) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        self._title.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 500;")
        header.addWidget(self._title)
        header.addStretch(1)
        self._reset_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")
        header.addWidget(self._reset_label)
        root.addLayout(header)

        bar_row = QHBoxLayout()
        bar_row.setSpacing(10)
        self._bar.setRange(0, 100)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(7)
        bar_row.addWidget(self._bar, 1)
        self._pct.setMinimumWidth(38)
        self._pct.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        bar_row.addWidget(self._pct)
        root.addLayout(bar_row)

        self._detail.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")
        root.addWidget(self._detail)

        self.update_values(used_percent, resets_at, used_tokens, limit_tokens)

    def update_values(
        self,
        used_percent: float | None,
        resets_at: str | None = None,
        used_tokens: str | None = None,
        limit_tokens: str | None = None,
    ) -> None:
        reset = _reset_hint(resets_at)
        self._reset_label.setText(reset)
        self._reset_label.setVisible(bool(reset))

        if used_percent is None:
            self._bar.hide()
            self._pct.hide()
            self._detail.hide()
            return

        self._bar.show()
        self._pct.show()
        value = int(min(100, max(0, used_percent)))
        if self._bar.value() != value:
            self._bar.setValue(value)
        color = usage_color(used_percent)
        self._bar.setStyleSheet(
            "QProgressBar {"
            f"  background: {BORDER_SUBTLE};"
            "  border: none;"
            "  border-radius: 4px;"
            "}"
            f"QProgressBar::chunk {{ background: {color}; border-radius: 4px; }}"
        )
        self._pct.setText(f"{used_percent:.0f}%")
        self._pct.setStyleSheet(
            f"color: {color}; font-size: 13px; font-weight: 700; letter-spacing: -0.3px;"
        )

        if used_tokens and limit_tokens:
            self._detail.setText(f"{used_tokens} of {limit_tokens}")
            self._detail.show()
        else:
            self._detail.hide()


class ProviderCard(QFrame):
    def __init__(self, provider: dict) -> None:
        super().__init__()
        provider_id = str(provider.get("id") or "")
        self._provider_id = provider_id
        style = provider_style(provider_id)
        self._accent = style["accent"]

        self.setStyleSheet(
            "ProviderCard {"
            f"  background: {BG_CARD};"
            f"  border: 1px solid {BORDER};"
            "  border-radius: 12px;"
            "}"
            "ProviderCard:hover {"
            f"  border-color: {self._accent}55;"
            "}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 12, 0)
        layout.setSpacing(0)

        self._accent_bar = QFrame()
        self._accent_bar.setFixedWidth(3)
        layout.addWidget(self._accent_bar)

        body = QVBoxLayout()
        body.setContentsMargins(12, 12, 0, 12)
        body.setSpacing(10)
        layout.addLayout(body, 1)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        self._badge = ProviderBadge(provider_id)
        title_row.addWidget(self._badge)

        name_col = QVBoxLayout()
        name_col.setSpacing(2)
        self._name = QLabel()
        self._name.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700;")
        name_col.addWidget(self._name)
        self._subtitle = QLabel()
        self._subtitle.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")
        name_col.addWidget(self._subtitle)
        title_row.addLayout(name_col, 1)

        meta_col = QVBoxLayout()
        meta_col.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self._plan = QLabel()
        self._plan.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._plan.setStyleSheet(
            f"color: {self._accent}; font-size: 10px; font-weight: 600; text-transform: capitalize;"
        )
        meta_col.addWidget(self._plan)
        self._active = QLabel()
        self._active.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._active.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")
        meta_col.addWidget(self._active)
        title_row.addLayout(meta_col)
        body.addLayout(title_row)

        self._limits_host = QVBoxLayout()
        self._limits_host.setSpacing(8)
        body.addLayout(self._limits_host)

        self._fallback = QLabel()
        self._fallback.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; line-height: 1.4;")
        self._fallback.setWordWrap(True)
        body.addWidget(self._fallback)

        self._limit_rows: list[UsageWindowRow] = []
        self.set_provider(provider)

    def set_provider(self, provider: dict) -> None:
        style = provider_style(str(provider.get("id") or self._provider_id))
        self._accent = style["accent"]
        self._accent_bar.setStyleSheet(
            f"background: {self._accent};"
            "border: none;"
            "border-top-left-radius: 12px;"
            "border-bottom-left-radius: 12px;"
        )

        self._name.setText(provider.get("label") or style["name"])

        subtitle_parts: list[str] = []
        if provider.get("subtitle"):
            subtitle_parts.append(str(provider["subtitle"]))
        if provider.get("model"):
            subtitle_parts.append(str(provider["model"]))
        if subtitle_parts:
            self._subtitle.setText(" · ".join(subtitle_parts))
            self._subtitle.show()
        else:
            self._subtitle.hide()

        if provider.get("plan_type"):
            self._plan.setText(str(provider["plan_type"]).capitalize())
            self._plan.show()
        else:
            self._plan.hide()

        if provider.get("active_sessions"):
            self._active.setText(f"{provider['active_sessions']} active")
            self._active.show()
        else:
            self._active.hide()

        limits = provider.get("limits") or []
        while len(self._limit_rows) < len(limits):
            row = UsageWindowRow("Limit", None)
            self._limit_rows.append(row)
            self._limits_host.addWidget(row)
        while len(self._limit_rows) > len(limits):
            row = self._limit_rows.pop()
            self._limits_host.removeWidget(row)
            row.deleteLater()

        if limits:
            self._limits_host.parentWidget().show() if self._limits_host.parentWidget() else None
            for row, limit in zip(self._limit_rows, limits, strict=False):
                row.update_values(
                    limit.get("used_percent"),
                    resets_at=limit.get("resets_at"),
                    used_tokens=limit.get("used_tokens_fmt"),
                    limit_tokens=limit.get("limit_tokens_fmt"),
                )
            self._fallback.hide()
        else:
            tokens = provider.get("total_tokens_fmt")
            self._fallback.setText(
                "No quota windows detected in local sessions."
                + (f"\n{tokens} tokens logged." if tokens else "")
            )
            self._fallback.show()


class UsagePanel(QWidget):
    refresh_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        apply_dropdown_window_flags(self)
        self.setFixedWidth(PANEL_WIDTH)
        self._generated_at: str | None = None
        self._digest: str | None = None
        self._cards: dict[str, ProviderCard] = {}
        self._pills: list[SummaryPill] = []
        self._empty_label: QLabel | None = None

        shell = QVBoxLayout(self)
        shell.setContentsMargins(8, 0, 8, 0)
        shell.setSpacing(0)

        self.caret = DropdownCaret()
        shell.addWidget(self.caret)

        self.body = QFrame()
        self.body.setObjectName("panelBody")
        self.body.setStyleSheet(
            f"#panelBody {{"
            f"  background: {BG};"
            f"  color: {TEXT};"
            f"  border: 1px solid {BORDER};"
            "  border-radius: 14px;"
            "}}"
        )
        shell.addWidget(self.body)

        outer = QVBoxLayout(self.body)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(10)

        brand_col = QVBoxLayout()
        brand_col.setSpacing(1)
        title = QLabel("Vektra AI Meter")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setWeight(QFont.Weight.Bold)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {TEXT}; letter-spacing: -0.2px;")
        brand_col.addWidget(title)
        subtitle = QLabel("AI usage limits")
        subtitle.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")
        brand_col.addWidget(subtitle)
        header.addLayout(brand_col)
        header.addStretch(1)

        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setFixedSize(30, 30)
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.setToolTip("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        self._icon_btn_style(self.refresh_btn)
        header.addWidget(self.refresh_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(self.hide)
        self._icon_btn_style(close_btn, danger=True)
        header.addWidget(close_btn)
        outer.addLayout(header)

        self.summary_host = QWidget()
        self.summary_layout = QHBoxLayout(self.summary_host)
        self.summary_layout.setContentsMargins(0, 0, 0, 0)
        self.summary_layout.setSpacing(6)
        outer.addWidget(self.summary_host)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {BORDER_SUBTLE}; border: none;")
        outer.addWidget(divider)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            "QScrollArea { background: transparent; }"
            f"QScrollBar:vertical {{ background: {BG_ELEVATED}; width: 6px; border-radius: 3px; }}"
            f"QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 3px; min-height: 24px; }}"
        )

        self.cards_host = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_host)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(10)
        self.scroll.setWidget(self.cards_host)
        outer.addWidget(self.scroll)

        self.footer = QLabel("")
        self.footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.footer.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")
        outer.addWidget(self.footer)

    def _icon_btn_style(self, button: QPushButton, *, danger: bool = False) -> None:
        hover = (
            "QPushButton:hover { background: #3f1212; color: #fca5a5; border-color: #7f1d1d; }"
            if danger
            else f"QPushButton:hover {{ background: {BORDER_SUBTLE}; color: {TEXT}; }}"
        )
        button.setStyleSheet(
            f"QPushButton {{"
            f"  background: {BG_ELEVATED};"
            f"  color: {TEXT_MUTED};"
            f"  border: 1px solid {BORDER};"
            "  border-radius: 8px;"
            "  font-size: 13px;"
            "  padding: 0;"
            "}"
            f"{hover}"
        )

    def set_refreshing(self, active: bool) -> None:
        self.refresh_btn.setEnabled(not active)
        self.refresh_btn.setText("…" if active else "↻")

    def set_footer_time(self, generated_at: str | None) -> None:
        self._generated_at = generated_at
        self.footer.setText(ago_label(generated_at))

    def tick_footer(self) -> None:
        if self._generated_at:
            self.footer.setText(ago_label(self._generated_at))

    def _build_summary(self, snapshot: dict) -> None:
        providers = snapshot.get("providers") or []
        pills_data: list[tuple[str, str, float]] = []

        for provider in providers:
            provider_id = str(provider.get("id") or "")
            style = provider_style(provider_id)
            short = style["name"].split()[0]
            peak: float | None = None
            peak_label = ""
            for limit in provider.get("limits") or []:
                used = limit.get("used_percent")
                if used is None or limit.get("label") == "Session":
                    continue
                if peak is None or float(used) > peak:
                    peak = float(used)
                    peak_label = str(limit.get("label") or "")
            if peak is not None:
                pills_data.append((f"{short} {peak_label} {peak:.0f}%", style["accent"], peak))

        while len(self._pills) < len(pills_data):
            pill = SummaryPill("", accent=TEXT_MUTED)
            self._pills.append(pill)
            self.summary_layout.insertWidget(self.summary_layout.count() - 1, pill)

        for index, pill in enumerate(self._pills):
            if index < len(pills_data):
                text, accent, percent = pills_data[index]
                pill.set_content(text, accent=accent, percent=percent)
                pill.show()
            else:
                pill.hide()

        if not pills_data:
            if self._empty_label is None:
                self._empty_label = QLabel("Waiting for quota data from local sessions")
                self._empty_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")
                self.summary_layout.insertWidget(0, self._empty_label)
            self._empty_label.show()
        elif self._empty_label is not None:
            self._empty_label.hide()

        stretch_item = self.summary_layout.itemAt(self.summary_layout.count() - 1)
        if stretch_item is None or stretch_item.spacerItem() is None:
            self.summary_layout.addStretch(1)

    def set_snapshot(self, snapshot: dict, *, digest: str | None = None) -> None:
        from ..util import snapshot_display_digest

        next_digest = digest or snapshot_display_digest(snapshot)
        data_changed = next_digest != self._digest
        self._digest = next_digest
        self.set_footer_time(snapshot.get("generated_at"))

        if data_changed:
            self._build_summary(snapshot)

            providers = [
                provider
                for provider in (snapshot.get("providers") or [])
                if provider.get("sessions", 0) > 0 or provider.get("limits")
            ]

            seen: set[str] = set()
            for provider in providers:
                provider_id = str(provider.get("id") or "")
                seen.add(provider_id)
                card = self._cards.get(provider_id)
                if card is None:
                    card = ProviderCard(provider)
                    self._cards[provider_id] = card
                    self.cards_layout.addWidget(card)
                else:
                    card.set_provider(provider)
                card.show()

            for provider_id, card in list(self._cards.items()):
                if provider_id not in seen:
                    card.hide()

            if not providers:
                if self._empty_label is None:
                    self._empty_label = QLabel("No provider sessions found on this machine.")
                    self._empty_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
                if self._empty_label.parent() is None:
                    self.cards_layout.addWidget(self._empty_label)
                self._empty_label.show()
            elif self._empty_label is not None:
                self._empty_label.hide()

        self._resize_to_content()

    def _resize_to_content(self) -> None:
        self.cards_host.adjustSize()
        self.adjustSize()
        max_h = min(self.sizeHint().height(), 580)
        self.setFixedHeight(max_h)

    def popup_near_tray(self, tray) -> None:
        show_panel_near_tray(self, tray)