from typing import Any

import customtkinter as ctk

from app.ui import theme


class StatusBadge(ctk.CTkLabel):
    def __init__(self, master: Any, text: str, tone: str = "muted") -> None:
        colors = {
            "success": (theme.SUCCESS, "#102A21"),
            "warning": (theme.WARNING, "#302715"),
            "error": (theme.ERROR, "#32191D"),
            "muted": (theme.TEXT_SECONDARY, theme.SURFACE),
        }
        foreground, background = colors.get(tone, colors["muted"])
        super().__init__(
            master,
            text=f"  {text}  ",
            text_color=foreground,
            fg_color=background,
            corner_radius=theme.SMALL_RADIUS,
            font=theme.FONT_SMALL,
        )
