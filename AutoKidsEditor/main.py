import customtkinter as ctk

from app.config import ensure_directories
from app.database.database import Database
from app.ui.main_window import MainWindow


def main() -> None:
    ensure_directories()
    Database()
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
