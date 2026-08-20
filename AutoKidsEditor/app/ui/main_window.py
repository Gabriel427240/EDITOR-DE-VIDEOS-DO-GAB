import shutil
import importlib.util
from tkinter import messagebox, simpledialog
from typing import Any

import customtkinter as ctk

from app.core.preset_manager import PresetManager
from app.core.project_manager import ProjectManager
from app.ui import theme
from app.ui.components.navigation_button import NavigationButton
from app.ui.components.stat_card import StatCard
from app.ui.components.status_badge import StatusBadge
from app.ui.project_details import ProjectDetailsFrame


class MainWindow(ctk.CTk):
    def __init__(self, project_manager: ProjectManager | None = None) -> None:
        super().__init__()
        self.project_manager = project_manager or ProjectManager()
        self.title("Editor de videos do gab")
        self.geometry("1280x800")
        self.minsize(1050, 680)
        theme.apply()
        self.configure(fg_color=theme.BACKGROUND)
        self._build_layout()
        self.show_home()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.sidebar = ctk.CTkFrame(self, width=236, corner_radius=0, fg_color=theme.SIDEBAR)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self._build_sidebar()
        self.content = ctk.CTkScrollableFrame(self, fg_color=theme.BACKGROUND, corner_radius=0)
        self.content.grid(row=0, column=1, padx=0, pady=0, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.search_value = ctk.StringVar()
        self.search_value.trace_add("write", lambda *_args: self.refresh_projects())

    def _build_sidebar(self) -> None:
        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=20, pady=(26, 32))
        ctk.CTkLabel(brand, text="[▣]", text_color=theme.PRIMARY, font=(theme.FONT_FAMILY, 24, "bold")).pack(anchor="w")
        ctk.CTkLabel(brand, text="Editor de videos\ndo Gab", text_color=theme.TEXT_PRIMARY, justify="left", font=(theme.FONT_FAMILY, 18, "bold")).pack(anchor="w", pady=(8, 0))
        ctk.CTkLabel(self.sidebar, text="WORKSPACE", text_color=theme.TEXT_MUTED, font=theme.FONT_SMALL).pack(fill="x", padx=24, pady=(0, 8))
        self.nav_buttons = {}
        for key, text, command in (
            ("home", "INÍCIO", self.show_home),
            ("new", "+  Novo projeto", self.create_project),
            ("projects", "PROJETOS", self.show_projects),
            ("settings", "CONFIGURAÇÕES", self.show_settings),
        ):
            button = NavigationButton(self.sidebar, text, command)
            button.pack(fill="x", padx=14, pady=3)
            self.nav_buttons[key] = button
        status = ctk.CTkFrame(self.sidebar, fg_color=theme.SURFACE, corner_radius=theme.SMALL_RADIUS)
        status.pack(side="bottom", fill="x", padx=16, pady=18)
        ctk.CTkLabel(status, text="SISTEMA", text_color=theme.TEXT_MUTED, font=theme.FONT_SMALL).pack(anchor="w", padx=12, pady=(10, 5))
        self._status_line(status, "FFMPEG", bool(shutil.which("ffmpeg")))
        self._status_line(status, "WHISPER", importlib.util.find_spec("faster_whisper") is not None)
        self._status_line(status, "OLLAMA", bool(shutil.which("ollama")))
        self._status_line(status, "IA LOCAL", False)
        ctk.CTkLabel(status, text="v0.1  •  CPU", text_color=theme.TEXT_MUTED, font=theme.FONT_SMALL).pack(anchor="w", padx=12, pady=(8, 10))

    @staticmethod
    def _status_line(parent: Any, label: str, online: bool) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=2)
        ctk.CTkLabel(row, text="●" if online else "○", text_color=theme.SUCCESS if online else theme.TEXT_MUTED, font=theme.FONT_SMALL).pack(side="left")
        ctk.CTkLabel(row, text=f"  {label}  "+("ATIVO" if online else "NÃO CONFIGURADA"), text_color=theme.TEXT_SECONDARY, font=theme.FONT_SMALL).pack(side="left")

    def _clear_content(self) -> None:
        for widget in self.content.winfo_children():
            widget.destroy()

    def _set_active(self, key: str) -> None:
        for name, button in self.nav_buttons.items():
            button.set_active(name == key)

    def create_project(self) -> None:
        name = simpledialog.askstring("NOVO PROJETO", "Como deseja chamar seu projeto?", parent=self)
        if name is None:
            return
        try:
            project = self.project_manager.create_project(name)
        except (ValueError, OSError) as error:
            messagebox.showerror("Não foi possível criar", str(error), parent=self)
            return
        self.open_project(project["id"])

    def show_home(self) -> None:
        self._set_active("home")
        self._clear_content()
        projects = self.project_manager.list_projects()
        self._build_dashboard(projects)

    def show_projects(self) -> None:
        self._set_active("projects")
        self._clear_content()
        self._build_dashboard(self.project_manager.list_projects(), title="Projetos")

    def refresh_projects(self) -> None:
        if self.nav_buttons.get("projects"):
            self.show_projects()

    def _build_dashboard(self, projects: list[dict[str, Any]], title: str = "Inicio") -> None:
        page = ctk.CTkFrame(self.content, fg_color="transparent")
        page.grid(row=0, column=0, padx=34, pady=30, sticky="ew")
        page.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkLabel(page, text="EDITOR DE VÍDEOS DO GAB", text_color=theme.TEXT_MUTED, font=theme.FONT_SMALL).grid(row=0, column=0, columnspan=3, sticky="w")
        ctk.CTkLabel(page, text="Olá", text_color=theme.TEXT_PRIMARY, font=theme.FONT_HERO).grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ctk.CTkLabel(page, text="Transforme suas mídias em vídeos prontos para publicar.", text_color=theme.TEXT_SECONDARY, font=theme.FONT_BODY).grid(row=2, column=0, columnspan=3, sticky="w", pady=(2, 24))
        hero = ctk.CTkFrame(page, fg_color=theme.PRIMARY, corner_radius=theme.RADIUS)
        hero.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0, 22))
        ctk.CTkLabel(hero, text="CRIE UM NOVO VÍDEO", text_color="#DCE8FF", font=theme.FONT_SMALL).pack(anchor="w", padx=24, pady=(22, 4))
        ctk.CTkLabel(hero, text="Adicione suas cenas, imagens e narração. O editor cuida da montagem.", text_color="white", font=theme.FONT_SECTION).pack(anchor="w", padx=24)
        ctk.CTkButton(hero, text="+  Criar novo projeto", command=self.create_project, fg_color="white", hover_color="#E8EEFF", text_color=theme.PRIMARY, corner_radius=theme.SMALL_RADIUS, height=38).pack(anchor="w", padx=24, pady=18)
        renders = sum(len(self.project_manager.database.list_project_renders(project["id"])) for project in projects)
        latest = projects[0]["name"] if projects else "Nenhum ainda"
        for index, (label, value, detail) in enumerate((("PROJETOS", str(len(projects)), "projetos criados"), ("VÍDEOS GERADOS", str(renders), "previews renderizados"), ("ÚLTIMO PROJETO", latest, "mais recente"))):
            StatCard(page, label, value, detail).grid(row=4, column=index, padx=(0 if index == 0 else 8, 8 if index < 2 else 0), sticky="ew")
        ctk.CTkLabel(page, text="PROJETOS RECENTES", text_color=theme.TEXT_PRIMARY, font=theme.FONT_TITLE).grid(row=5, column=0, columnspan=3, sticky="w", pady=(30, 12))
        if title == "Projetos":
            search = ctk.CTkEntry(page, textvariable=self.search_value, placeholder_text="Buscar projeto...", height=36)
            search.grid(row=5, column=2, sticky="e", pady=(30, 12))
        recent = ctk.CTkFrame(page, fg_color="transparent")
        recent.grid(row=6, column=0, columnspan=3, sticky="ew")
        recent.grid_columnconfigure((0, 1), weight=1)
        if not projects:
            empty = ctk.CTkFrame(recent, fg_color=theme.CARD, border_color=theme.BORDER, border_width=1, corner_radius=theme.RADIUS)
            empty.grid(row=0, column=0, columnspan=2, sticky="ew")
            ctk.CTkLabel(empty, text="Nenhum projeto ainda", text_color=theme.TEXT_PRIMARY, font=theme.FONT_TITLE).pack(pady=(28, 4))
            ctk.CTkLabel(empty, text="Crie seu primeiro projeto para comecar.", text_color=theme.TEXT_SECONDARY, font=theme.FONT_BODY).pack()
            ctk.CTkButton(empty, text="Criar projeto", command=self.create_project, width=150).pack(pady=22)
        else:
            filtered = self.filter_projects(projects, self.search_value.get())
            for index, project in enumerate(filtered[:10]):
                self._project_card(recent, project, index // 2, index % 2)

    @staticmethod
    def filter_projects(projects: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
        normalized_query = query.strip().lower()
        return [
            project
            for project in projects
            if normalized_query in project["name"].lower()
        ]

    def _project_card(self, parent: Any, project: dict[str, Any], row: int, column: int) -> None:
        media = self.project_manager.list_project_media(project["id"])
        timeline = self.project_manager.get_project_timeline(project["id"])
        videos = sum(item["media_type"] == "video" for item in media)
        images = sum(item["media_type"] == "image" for item in media)
        card = ctk.CTkFrame(parent, fg_color=theme.CARD, border_color=theme.BORDER, border_width=1, corner_radius=theme.RADIUS)
        card.grid(row=row, column=column, padx=(0, 8) if column == 0 else (8, 0), pady=6, sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text=project["name"], text_color=theme.TEXT_PRIMARY, font=theme.FONT_SECTION, anchor="w").grid(row=0, column=0, padx=18, pady=(16, 3), sticky="w")
        ctk.CTkLabel(card, text=PresetManager.get_preset(project.get("preset", "kids_story_v1")).NAME, text_color=theme.TEXT_MUTED, font=theme.FONT_SMALL, anchor="w").grid(row=1, column=0, padx=18, sticky="w")
        ctk.CTkLabel(card, text=f"{videos} vídeos  •  {images} imagens", text_color=theme.TEXT_SECONDARY, font=theme.FONT_SMALL, anchor="w").grid(row=2, column=0, padx=18, pady=(12, 0), sticky="w")
        ctk.CTkLabel(card, text=f"●  TIMELINE {'PRONTA' if timeline else 'PENDENTE'}", text_color=theme.SUCCESS if timeline else theme.WARNING, font=theme.FONT_SMALL, anchor="w").grid(row=3, column=0, padx=18, pady=(2, 0), sticky="w")
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=4, column=0, padx=18, pady=(12, 16), sticky="w")
        ctk.CTkButton(actions, text="Abrir", command=lambda project_id=project["id"]: self.open_project(project_id), width=82, height=30).pack(side="left")
        ctk.CTkButton(actions, text="⋯", command=lambda project_id=project["id"]: self.show_project_menu(project_id), width=34, height=30, fg_color="transparent", hover_color=theme.CARD_HOVER, text_color=theme.TEXT_SECONDARY).pack(side="left", padx=(8, 0))

    def show_project_menu(self, project_id: int) -> None:
        menu = ctk.CTkToplevel(self)
        menu.title("Ações do projeto")
        menu.geometry("190x150")
        menu.resizable(False, False)
        menu.configure(fg_color=theme.SURFACE)
        ctk.CTkButton(menu, text="Abrir", command=lambda: (menu.destroy(), self.open_project(project_id))).pack(fill="x", padx=14, pady=(14, 4))
        ctk.CTkButton(menu, text="Abrir pasta", command=lambda: (menu.destroy(), self.open_project_folder(project_id)), fg_color="transparent", hover_color=theme.CARD_HOVER).pack(fill="x", padx=14, pady=4)
        ctk.CTkButton(menu, text="Renomear", command=lambda: (menu.destroy(), self.rename_project(project_id)), fg_color="transparent", hover_color=theme.CARD_HOVER).pack(fill="x", padx=14, pady=4)
        ctk.CTkButton(menu, text="Excluir projeto", command=lambda: (menu.destroy(), self.delete_project(project_id)), fg_color="transparent", hover_color=theme.CARD_HOVER, text_color=theme.ERROR).pack(fill="x", padx=14, pady=4)

    def open_project_folder(self, project_id: int) -> None:
        project = self.project_manager.get_project(project_id)
        folder = project["folder_path"]
        if folder:
            import os
            os.startfile(folder)

    def rename_project(self, project_id: int) -> None:
        project = self.project_manager.get_project(project_id)
        name = simpledialog.askstring("Renomear projeto", "Nome do projeto", initialvalue=project["name"], parent=self)
        if name is None:
            return
        try:
            self.project_manager.rename_project(project_id, name)
            self.show_toast("✓  Projeto renomeado")
            self.show_projects()
        except (ValueError, RuntimeError) as error:
            messagebox.showerror("Não foi possível renomear", str(error), parent=self)

    def delete_project(self, project_id: int) -> None:
        project = self.project_manager.get_project(project_id)
        dialog = ctk.CTkToplevel(self)
        dialog.title("Excluir projeto")
        dialog.geometry("420x230")
        dialog.resizable(False, False)
        dialog.configure(fg_color=theme.SURFACE)
        ctk.CTkLabel(dialog, text="EXCLUIR PROJETO?", font=theme.FONT_TITLE, text_color=theme.TEXT_PRIMARY).pack(anchor="w", padx=24, pady=(24, 8))
        ctk.CTkLabel(dialog, text=f"Esta ação removerá o projeto e seus arquivos importados.\n\n{project['name']}", text_color=theme.TEXT_SECONDARY, justify="left").pack(anchor="w", padx=24)
        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(side="bottom", fill="x", padx=24, pady=20)
        ctk.CTkButton(buttons, text="Cancelar", command=dialog.destroy, fg_color="transparent", hover_color=theme.CARD_HOVER).pack(side="right", padx=(8, 0))
        ctk.CTkButton(buttons, text="Excluir projeto", command=lambda: self._confirm_delete(dialog, project_id), fg_color=theme.ERROR, hover_color="#F08089").pack(side="right")

    def _confirm_delete(self, dialog: ctk.CTkToplevel, project_id: int) -> None:
        try:
            self.project_manager.delete_project(project_id)
            dialog.destroy()
            self.show_toast("✓  Projeto excluído")
            self.show_projects()
        except (RuntimeError, OSError) as error:
            messagebox.showerror("Não foi possível excluir", str(error), parent=self)

    def show_toast(self, message: str) -> None:
        toast = ctk.CTkLabel(self, text=message, fg_color=theme.SUCCESS, text_color="#071A12", corner_radius=theme.SMALL_RADIUS, font=theme.FONT_BODY)
        toast.place(relx=0.98, rely=0.94, anchor="se")
        self.after(2800, toast.destroy)

    def open_project(self, project_id: int) -> None:
        try:
            project = self.project_manager.get_project(project_id)
        except RuntimeError as error:
            messagebox.showerror("Erro", str(error), parent=self)
            return
        self._set_active("projects")
        self._clear_content()
        ProjectDetailsFrame(self.content, project, self.project_manager, self.show_home).grid(row=0, column=0, padx=26, pady=24, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)

    def show_settings(self) -> None:
        self._set_active("settings")
        self._clear_content()
        page = ctk.CTkFrame(self.content, fg_color="transparent")
        page.grid(row=0, column=0, padx=34, pady=30, sticky="ew")
        page.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(page, text="CONFIGURACOES", text_color=theme.TEXT_MUTED, font=theme.FONT_SMALL).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(page, text="Preferencias do editor", text_color=theme.TEXT_PRIMARY, font=theme.FONT_HERO).grid(row=1, column=0, sticky="w", pady=(6, 26))
        self._settings_card(page, 2, "APARENCIA", (("Tema", "Dark"),))
        self._settings_card(page, 3, "EDITOR", (("Preset padrao", "Kids Story V1"),))
        self._settings_card(page, 4, "SISTEMA", (("FFmpeg", "Detectado" if shutil.which("ffmpeg") else "Nao encontrado"), ("FFprobe", "Detectado" if shutil.which("ffprobe") else "Nao encontrado"), ("IA Local", "Nao configurada"), ("GPU", "Nao configurada")))

    def _settings_card(self, parent: Any, row: int, title: str, entries: tuple[tuple[str, str], ...]) -> None:
        card = ctk.CTkFrame(parent, fg_color=theme.CARD, border_color=theme.BORDER, border_width=1, corner_radius=theme.RADIUS)
        card.grid(row=row, column=0, pady=8, sticky="ew")
        card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(card, text=title, text_color=theme.TEXT_MUTED, font=theme.FONT_SMALL).grid(row=0, column=0, padx=18, pady=(14, 8), sticky="w")
        for index, (label, value) in enumerate(entries, start=1):
            ctk.CTkLabel(card, text=label, text_color=theme.TEXT_SECONDARY, font=theme.FONT_BODY).grid(row=index, column=0, padx=18, pady=7, sticky="w")
            tone = "success" if value == "Detectado" else "muted"
            StatusBadge(card, value, tone).grid(row=index, column=1, padx=18, pady=7, sticky="e")
        card.grid_rowconfigure(len(entries), pad=8)
