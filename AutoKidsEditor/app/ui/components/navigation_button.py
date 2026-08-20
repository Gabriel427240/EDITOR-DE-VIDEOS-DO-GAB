from typing import Any, Callable

import customtkinter as ctk

from app.ui import theme


class NavigationButton(ctk.CTkButton):
    def __init__(self, master: Any, text: str, command: Callable[[], None]) -> None:
        super().__init__(
            master,
            text=text,
            command=command,
            anchor="w",
            height=40,
            corner_radius=theme.SMALL_RADIUS,
            fg_color="transparent",
            hover_color=theme.CARD_HOVER,
            text_color=theme.TEXT_SECONDARY,
            font=theme.FONT_BODY,
        )

    def set_active(self, active: bool) -> None:
        self.configure(
            fg_color=theme.PRIMARY if active else "transparent",
            hover_color=theme.PRIMARY_HOVER if active else theme.CARD_HOVER,
            text_color=theme.TEXT_PRIMARY if active else theme.TEXT_SECONDARY,
        )
