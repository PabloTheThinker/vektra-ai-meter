from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygon
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
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


def _ago_label(iso_value: str | None) -> str:
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
        self.setFixedSize(28, 28)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            "QLabel {"
            f"  background: {style['accent']}22;"
            f"  color: {style['accent']};"
            "  border-radius: 8px;"
            "  font-size: 11px;"
            "  font-weight: 700;"
            "  letter-spacing: -0.3px;"
            "}"
        )


class SummaryPill(QLabel):
    def __init__(self, text: str, *, accent: str, percent: float | None = None) -> None:
        super().__init__(text)
        border = usage_color(percent) if percent is not None else BORDER
        self.setStyleSheet(
            "QLabel {"
            f"  background: {accent}18;"
            f"  color: {TEXT};"
            f"  border: 1px solid {border}44;"
            "  border-radius: 999px;"
            "  padding: 4px 10px;"
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
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel(window_title(label))
        title.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 500;")
        header.addWidget(title)
        header.addStretch(1)

        reset = _reset_hint(resets_at)
        if reset:
            reset_label = QLabel(reset)
            reset_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")
            header.addWidget(reset_label)

        root.addLayout(header)

        if used_percent is not None:
            bar_row = QHBoxLayout()
            bar_row.setSpacing(10)

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(int(min(100, max(0, used_percent))))
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            color = usage_color(used_percent)
            bar.setStyleSheet(
                "QProgressBar {"
                f"  background: {BORDER_SUBTLE};"
                "  border: none;"
                "  border-radius: 3px;"
                "}"
                f"QProgressBar::chunk {{ background: {color}; border-radius: 3px; }}"
            )
            bar_row.addWidget(bar, 1)

            pct = QLabel(f"{used_percent:.0f}%")
            pct.setMinimumWidth(36)
            pct.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            pct.setStyleSheet(
                f"color: {color}; font-size: 13px; font-weight: 700; letter-spacing: -0.3px;"
            )
            bar_row.addWidget(pct)
            root.addLayout(bar_row)

            if used_tokens and limit_tokens:
                detail = QLabel(f"{used_tokens} of {limit_tokens}")
                detail.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")
                root.addWidget(detail)


class ProviderCard(QFrame):
    def __init__(self, provider: dict) -> None:
        super().__init__()
        provider_id = str(provider.get("id") or "")
        style = provider_style(provider_id)
        accent = style["accent"]

        self.setStyleSheet(
            "ProviderCard {"
            f"  background: {BG_CARD};"
            f"  border: 1px solid {BORDER};"
            "  border-radius: 12px;"
            "}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 12, 0)
        layout.setSpacing(0)

        accent_bar = QFrame()
        accent_bar.setFixedWidth(3)
        accent_bar.setStyleSheet(
            f"background: {accent};"
            "border: none;"
            "border-top-left-radius: 12px;"
            "border-bottom-left-radius: 12px;"
        )
        layout.addWidget(accent_bar)

        body = QVBoxLayout()
        body.setContentsMargins(12, 12, 0, 12)
        body.setSpacing(10)
        layout.addLayout(body, 1)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        title_row.addWidget(ProviderBadge(provider_id))

        name_col = QVBoxLayout()
        name_col.setSpacing(2)
        name = QLabel(provider.get("label") or style["name"])
        name.setStyleSheet(f"color: {TEXT}; font-size: 13px; font-weight: 700;")
        name_col.addWidget(name)

        subtitle_parts: list[str] = []
        if provider.get("subtitle"):
            subtitle_parts.append(str(provider["subtitle"]))
        if provider.get("model"):
            subtitle_parts.append(str(provider["model"]))
        if subtitle_parts:
            subtitle = QLabel(" · ".join(subtitle_parts))
            subtitle.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")
            name_col.addWidget(subtitle)
        title_row.addLayout(name_col, 1)

        meta_col = QVBoxLayout()
        meta_col.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        if provider.get("plan_type"):
            plan = QLabel(str(provider["plan_type"]).capitalize())
            plan.setAlignment(Qt.AlignmentFlag.AlignRight)
            plan.setStyleSheet(
                f"color: {accent}; font-size: 10px; font-weight: 600; text-transform: capitalize;"
            )
            meta_col.addWidget(plan)
        if provider.get("active_sessions"):
            active = QLabel(f"{provider['active_sessions']} active")
            active.setAlignment(Qt.AlignmentFlag.AlignRight)
            active.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")
            meta_col.addWidget(active)
        title_row.addLayout(meta_col)
        body.addLayout(title_row)

        limits = provider.get("limits") or []
        if limits:
            for limit in limits:
                body.addWidget(
                    UsageWindowRow(
                        label=str(limit.get("label") or "Limit"),
                        used_percent=limit.get("used_percent"),
                        resets_at=limit.get("resets_at"),
                        used_tokens=limit.get("used_tokens_fmt"),
                        limit_tokens=limit.get("limit_tokens_fmt"),
                    )
                )
        else:
            tokens = provider.get("total_tokens_fmt")
            fallback = QLabel(
                "No quota windows detected in local sessions."
                + (f"\n{tokens} tokens logged." if tokens else "")
            )
            fallback.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; line-height: 1.4;")
            fallback.setWordWrap(True)
            body.addWidget(fallback)


class UsagePanel(QWidget):
    refresh_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        apply_dropdown_window_flags(self)
        self.setFixedWidth(PANEL_WIDTH)

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
        shadow = QGraphicsDropShadowEffect(self.body)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 70))
        self.body.setGraphicsEffect(shadow)
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

        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(30, 30)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setToolTip("Refresh")
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        refresh_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: {BG_ELEVATED};"
            f"  color: {TEXT_MUTED};"
            f"  border: 1px solid {BORDER};"
            "  border-radius: 8px;"
            "  font-size: 14px;"
            "  padding: 0;"
            "}"
            f"QPushButton:hover {{ background: {BORDER_SUBTLE}; color: {TEXT}; }}"
        )
        header.addWidget(refresh_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(self.hide)
        close_btn.setStyleSheet(
            f"QPushButton {{"
            f"  background: {BG_ELEVATED};"
            f"  color: {TEXT_MUTED};"
            f"  border: 1px solid {BORDER};"
            "  border-radius: 8px;"
            "  font-size: 12px;"
            "  padding: 0;"
            "}"
            f"QPushButton:hover {{ background: #3f1212; color: #fca5a5; border-color: #7f1d1d; }}"
        )
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
            f"QScrollArea {{ background: transparent; }}"
            f"QScrollBar:vertical {{"
            f"  background: {BG_ELEVATED};"
            "  width: 6px;"
            "  border-radius: 3px;"
            "}"
            f"QScrollBar::handle:vertical {{"
            f"  background: {BORDER};"
            "  border-radius: 3px;"
            "  min-height: 24px;"
            "}}"
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

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _build_summary(self, snapshot: dict) -> None:
        self._clear_layout(self.summary_layout)
        providers = snapshot.get("providers") or []
        added = False

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
                text = f"{short} {peak_label} {peak:.0f}%"
                self.summary_layout.addWidget(
                    SummaryPill(text, accent=style["accent"], percent=peak)
                )
                added = True

        if not added:
            empty = QLabel("Waiting for quota data from local sessions")
            empty.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")
            self.summary_layout.addWidget(empty)

        self.summary_layout.addStretch(1)

    def set_snapshot(self, snapshot: dict) -> None:
        self._build_summary(snapshot)
        self.footer.setText(_ago_label(snapshot.get("generated_at")))

        self._clear_layout(self.cards_layout)

        providers = snapshot.get("providers") or []
        if not providers:
            empty = QLabel("No provider sessions found on this machine.")
            empty.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
            self.cards_layout.addWidget(empty)
        else:
            for provider in providers:
                if provider.get("sessions", 0) > 0 or provider.get("limits"):
                    self.cards_layout.addWidget(ProviderCard(provider))

        self.cards_layout.addStretch(1)
        self.adjustSize()
        max_h = min(self.sizeHint().height(), 580)
        self.setFixedHeight(max_h)

    def popup_near_tray(self, tray) -> None:
        show_panel_near_tray(self, tray)