from typing import Any, Callable

import customtkinter as ctk

from app.ui import theme


class StatCard(ctk.CTkFrame):
    def __init__(
        self,
        master: Any,
        label: str,
        value: str,
        detail: str,
        command: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(master, fg_color=theme.CARD, border_color=theme.BORDER, border_width=1, corner_radius=theme.RADIUS)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=label.upper(), text_color=theme.TEXT_MUTED, font=theme.FONT_SMALL, anchor="w").grid(row=0, column=0, padx=18, pady=(16, 4), sticky="w")
        value_label = ctk.CTkLabel(self, text=value, text_color=theme.TEXT_PRIMARY, font=(theme.FONT_FAMILY, 24, "bold"), anchor="w")
        value_label.grid(row=1, column=0, padx=18, pady=(0, 2), sticky="w")
        ctk.CTkLabel(self, text=detail, text_color=theme.TEXT_SECONDARY, font=theme.FONT_SMALL, anchor="w").grid(row=2, column=0, padx=18, pady=(0, 16), sticky="w")
        if command is not None:
            self.bind("<Button-1>", lambda _event: command())
            for child in self.winfo_children():
                child.bind("<Button-1>", lambda _event: command())
