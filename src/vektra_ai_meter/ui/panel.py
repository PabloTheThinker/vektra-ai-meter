from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt, Signal
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

from .wayland import show_panel_near_tray


def _usage_color_css(percent: float) -> str:
    if percent >= 85:
        return "#ef4444"
    if percent >= 60:
        return "#f59e0b"
    return "#22c55e"


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
            return "resets soon"
        if minutes < 60:
            return f"resets in {minutes}m"
        hours = minutes // 60
        if hours < 48:
            return f"resets in {hours}h"
        days = hours // 24
        return f"resets in {days}d"
    except ValueError:
        return ""


class LimitRow(QWidget):
    def __init__(
        self,
        label: str,
        used_percent: float | None,
        *,
        detail: str = "",
        resets_at: str | None = None,
        remaining_percent: float | None = None,
        used_tokens: str | None = None,
        limit_tokens: str | None = None,
    ) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel(label)
        title.setStyleSheet("color: #d4d4d8; font-size: 12px; font-weight: 500;")
        header.addWidget(title)
        header.addStretch(1)

        if used_percent is not None:
            pct = QLabel(f"{used_percent:.0f}%")
            pct.setStyleSheet(
                f"color: {_usage_color_css(used_percent)}; font-size: 12px; font-weight: 700;"
            )
            header.addWidget(pct)
            if remaining_percent is not None:
                remain = QLabel(f"{remaining_percent:.0f}% left")
                remain.setStyleSheet("color: #71717a; font-size: 10px; margin-left: 6px;")
                header.addWidget(remain)
        elif detail:
            meta = QLabel(detail)
            meta.setStyleSheet("color: #a1a1aa; font-size: 11px;")
            header.addWidget(meta)

        root.addLayout(header)

        if used_percent is not None:
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(int(min(100, max(0, used_percent))))
            bar.setTextVisible(False)
            bar.setFixedHeight(8)
            color = _usage_color_css(used_percent)
            bar.setStyleSheet(
                "QProgressBar {"
                "  background: #27272a;"
                "  border: none;"
                "  border-radius: 4px;"
                "}"
                f"QProgressBar::chunk {{ background: {color}; border-radius: 4px; }}"
            )
            root.addWidget(bar)

            meta_parts: list[str] = []
            if used_tokens and limit_tokens:
                meta_parts.append(f"{used_tokens} / {limit_tokens}")
            elif detail:
                meta_parts.append(detail)
            hint = _reset_hint(resets_at)
            if hint:
                meta_parts.append(hint)
            if meta_parts:
                meta = QLabel(" · ".join(meta_parts))
                meta.setStyleSheet("color: #71717a; font-size: 10px;")
                root.addWidget(meta)


class ProviderCard(QFrame):
    def __init__(self, provider: dict) -> None:
        super().__init__()
        self.setStyleSheet(
            "ProviderCard {"
            "  background: #18181b;"
            "  border: 1px solid #27272a;"
            "  border-radius: 10px;"
            "}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        title_row = QHBoxLayout()
        name = QLabel(provider.get("label") or provider.get("id", "Provider"))
        name.setStyleSheet("color: #fafafa; font-size: 13px; font-weight: 600;")
        title_row.addWidget(name)
        title_row.addStretch(1)

        plan = provider.get("plan_type")
        if plan:
            plan_label = QLabel(str(plan))
            plan_label.setStyleSheet("color: #a78bfa; font-size: 10px; text-transform: capitalize;")
            title_row.addWidget(plan_label)

        if provider.get("active_sessions"):
            active = QLabel(f"{provider['active_sessions']} active")
            active.setStyleSheet("color: #71717a; font-size: 11px;")
            title_row.addWidget(active)

        layout.addLayout(title_row)

        limits = provider.get("limits") or []
        if limits:
            for limit in limits:
                layout.addWidget(
                    LimitRow(
                        label=str(limit.get("label") or "Limit"),
                        used_percent=limit.get("used_percent"),
                        detail=str(limit.get("detail") or ""),
                        resets_at=limit.get("resets_at"),
                        remaining_percent=limit.get("remaining_percent"),
                        used_tokens=limit.get("used_tokens_fmt"),
                        limit_tokens=limit.get("limit_tokens_fmt"),
                    )
                )
        else:
            tokens = provider.get("total_tokens_fmt")
            fallback = QLabel(
                f"No quota windows in local sessions."
                + (f" ({tokens} logged)" if tokens else "")
            )
            fallback.setStyleSheet("color: #71717a; font-size: 11px;")
            fallback.setWordWrap(True)
            layout.addWidget(fallback)


class UsagePanel(QWidget):
    refresh_requested = Signal()
    quit_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedWidth(340)
        self.setStyleSheet(
            "background: #09090b; color: #fafafa; border: 1px solid #27272a; border-radius: 12px;"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 12)
        outer.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Vektra AI Meter")
        title.setStyleSheet("font-size: 14px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch(1)
        self.peak_label = QLabel("")
        self.peak_label.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        header.addWidget(self.peak_label)
        outer.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; }")

        self.cards_host = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_host)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(8)
        self.scroll.setWidget(self.cards_host)
        outer.addWidget(self.scroll)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        quit_btn = QPushButton("Quit")
        quit_btn.clicked.connect(self.quit_requested.emit)
        for btn in (refresh_btn, quit_btn):
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setStyleSheet(
                "QPushButton {"
                "  background: #27272a;"
                "  color: #fafafa;"
                "  border: none;"
                "  border-radius: 8px;"
                "  padding: 8px 12px;"
                "}"
                "QPushButton:hover { background: #3f3f46; }"
            )
        actions.addWidget(refresh_btn)
        actions.addWidget(quit_btn)
        outer.addLayout(actions)

    def set_snapshot(self, snapshot: dict) -> None:
        summary = snapshot.get("summary") or {}
        peak = summary.get("peak_percent_fmt")
        peak_label = summary.get("peak_label")
        if peak and peak != "—" and peak_label:
            self.peak_label.setText(f"{peak_label} {peak}")
        elif peak and peak != "—":
            self.peak_label.setText(f"Peak {peak}")
        else:
            self.peak_label.setText(summary.get("total_tokens_fmt", ""))

        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        providers = snapshot.get("providers") or []
        if not providers:
            empty = QLabel("No provider sessions found.")
            empty.setStyleSheet("color: #71717a; font-size: 12px;")
            self.cards_layout.addWidget(empty)
        else:
            for provider in providers:
                self.cards_layout.addWidget(ProviderCard(provider))

        self.cards_layout.addStretch(1)
        self.adjustSize()
        max_h = min(self.sizeHint().height(), 560)
        self.setFixedHeight(max_h)

    def popup_near_tray(self, tray) -> None:
        show_panel_near_tray(self, tray)