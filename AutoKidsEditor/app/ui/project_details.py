import os
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Callable

import customtkinter as ctk

from app.core.preset_manager import PresetManager
from app.core.project_manager import ProjectManager
from app.services.video_renderer import VideoRenderError
from app.ui import theme
from app.ui.components.status_badge import StatusBadge


def format_duration(seconds: float | int | None) -> str:
    if seconds is None or seconds < 0:
        return "Metadados indisponiveis"
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds_part = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds_part:02d}" if hours else f"{minutes:02d}:{seconds_part:02d}"


class ProjectDetailsFrame(ctk.CTkScrollableFrame):
    def __init__(self, master: Any, project: dict[str, Any], project_manager: ProjectManager, on_back: Callable[[], None]) -> None:
        super().__init__(master, fg_color=theme.BACKGROUND, corner_radius=0)
        self.project = project
        self.project_manager = project_manager
        self.on_back = on_back
        self.media_expanded = False
        self.timeline_expanded = False
        self.last_output_path: Path | None = None
        self.grid_columnconfigure(0, weight=1)
        self._build_layout()
        self.refresh_media()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(4, 18))
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(header, text="←  PROJETOS", command=self.on_back, width=105, fg_color="transparent", hover_color=theme.CARD_HOVER, text_color=theme.TEXT_SECONDARY).grid(row=0, column=0, padx=(0, 16))
        ctk.CTkLabel(header, text=self.project["name"], text_color=theme.TEXT_PRIMARY, font=theme.FONT_TITLE).grid(row=0, column=1, sticky="w")
        preset_name = self.project.get("preset", PresetManager.DEFAULT_PRESET)
        ctk.CTkLabel(header, text="Preset", text_color=theme.TEXT_MUTED, font=theme.FONT_SMALL).grid(row=0, column=2, padx=(10, 6))
        ctk.CTkLabel(header, text=PresetManager.get_preset(preset_name).NAME, text_color=theme.TEXT_PRIMARY, fg_color=theme.SURFACE, corner_radius=theme.SMALL_RADIUS, font=theme.FONT_SMALL).grid(row=0, column=3, padx=(0, 8), ipady=5, ipadx=8)
        self.status_badge = StatusBadge(header, "Configuracao incompleta", "warning")
        self.status_badge.grid(row=0, column=4)
        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=5, padx=(12, 0))
        ctk.CTkButton(actions, text="Renomear", command=self.rename_project, width=88, height=30, fg_color=theme.SURFACE, hover_color=theme.CARD_HOVER).pack(side="left", padx=3)
        ctk.CTkButton(actions, text="⋯", command=self.show_actions, width=34, height=30, fg_color="transparent", hover_color=theme.CARD_HOVER, text_color=theme.TEXT_SECONDARY).pack(side="left", padx=3)

        self.stepper = ctk.CTkFrame(self, fg_color=theme.SURFACE, corner_radius=theme.RADIUS)
        self.stepper.grid(row=1, column=0, sticky="ew", pady=(0, 18))
        self.step_labels: list[ctk.CTkLabel] = []
        for index, label in enumerate(("1  MIDIAS", "2  NARRACAO", "3  TIMELINE", "4  RENDER")):
            if index:
                ctk.CTkLabel(self.stepper, text="—", text_color=theme.BORDER, font=theme.FONT_BODY).grid(row=0, column=index * 2 - 1, pady=13)
            item = ctk.CTkLabel(self.stepper, text=label, text_color=theme.TEXT_MUTED, font=theme.FONT_SMALL)
            item.grid(row=0, column=index * 2, padx=14, pady=13)
            self.step_labels.append(item)

        self.summary_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.summary_frame.grid(row=2, column=0, sticky="ew", pady=(0, 20))
        self.summary_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.media_section = self._section_shell("MÍDIAS DO PROJETO", 3)
        self.media_summary = ctk.CTkFrame(self.media_section, fg_color="transparent")
        self.media_summary.pack(fill="x", padx=14, pady=(2, 10))
        self.media_summary.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.media_expand_frame = ctk.CTkFrame(self.media_section, fg_color="transparent")
        self.media_expand_button = ctk.CTkButton(self.media_section, text="Ver arquivos", command=self.toggle_media, width=120, fg_color="transparent", hover_color=theme.CARD_HOVER, text_color=theme.PRIMARY)
        self.media_expand_button.pack(anchor="w", padx=14, pady=(0, 12))

        self.timeline_section = self._section_shell("TIMELINE", 4)
        self.timeline_frame = ctk.CTkScrollableFrame(self.timeline_section, height=210, fg_color="transparent")
        self.timeline_frame.pack(fill="x", padx=12, pady=(0, 4))
        self.timeline_toggle = ctk.CTkButton(self.timeline_section, text="Ver timeline completa", command=self.toggle_timeline, width=170, fg_color="transparent", hover_color=theme.CARD_HOVER, text_color=theme.PRIMARY)
        self.timeline_toggle.pack(anchor="w", padx=14, pady=(0, 12))

        self.scenes_section = self._section_shell("CENAS DA HISTÓRIA", 5)
        self.scenes_frame = ctk.CTkFrame(self.scenes_section, fg_color="transparent")
        self.scenes_frame.pack(fill="x", padx=14, pady=(0, 12))

        self.render_section = self._section_shell("RENDERIZAÇÃO", 6)
        self._build_render_section()

    def _section_shell(self, title: str, row: int) -> ctk.CTkFrame:
        shell = ctk.CTkFrame(self, fg_color=theme.SURFACE, border_color=theme.BORDER, border_width=1, corner_radius=theme.RADIUS)
        shell.grid(row=row, column=0, sticky="ew", pady=(0, 18))
        ctk.CTkLabel(shell, text=title, text_color=theme.TEXT_PRIMARY, font=theme.FONT_SECTION).pack(anchor="w", padx=18, pady=(15, 7))
        return shell

    def _build_render_section(self) -> None:
        body = ctk.CTkFrame(self.render_section, fg_color="transparent")
        body.pack(fill="x", padx=18, pady=(0, 16))
        body.grid_columnconfigure(0, weight=1)
        self.render_info = ctk.CTkLabel(body, text="Gere uma timeline para preparar o preview.", text_color=theme.TEXT_SECONDARY, font=theme.FONT_BODY, justify="left", anchor="w")
        self.render_info.grid(row=0, column=0, sticky="w")
        self.render_button = ctk.CTkButton(body, text="▶  GERAR VIDEO", command=self.render_preview, height=42, width=190, state="disabled", fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER, font=theme.FONT_SECTION)
        self.render_button.grid(row=0, column=1, padx=(20, 0))
        ai_actions = ctk.CTkFrame(body, fg_color="transparent")
        ai_actions.grid(row=4, column=0, columnspan=2, sticky="w", pady=(14, 0))
        ctk.CTkButton(ai_actions, text="Transcrever narração", command=self.transcribe_narration, width=160, height=30, fg_color=theme.SURFACE, hover_color=theme.CARD_HOVER).pack(side="left", padx=(0, 6))
        ctk.CTkButton(ai_actions, text="Analisar história", command=self.analyze_story, width=145, height=30, fg_color=theme.SURFACE, hover_color=theme.CARD_HOVER).pack(side="left", padx=6)
        ctk.CTkButton(ai_actions, text="✦  Preparar com IA", command=self.prepare_with_ai, width=145, height=30, fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER).pack(side="left", padx=6)
        self.progress_bar = ctk.CTkProgressBar(body, height=8)
        self.progress_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(16, 5))
        self.progress_bar.set(0)
        self.render_status_label = ctk.CTkLabel(body, text="Pronto", text_color=theme.TEXT_MUTED, font=theme.FONT_SMALL)
        self.render_status_label.grid(row=2, column=0, columnspan=2, sticky="w")
        self.result_frame = ctk.CTkFrame(body, fg_color=theme.CARD, corner_radius=theme.SMALL_RADIUS)
        self.result_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        self.result_frame.grid_remove()

    def refresh_media(self) -> None:
        media = self.project_manager.list_project_media(self.project["id"])
        timeline = self.project_manager.get_project_timeline(self.project["id"])
        self._refresh_summary(media, timeline)
        self._refresh_media_cards(media)
        self._refresh_timeline(timeline, media)
        self._refresh_scenes()
        self._update_flow(media, timeline)
        self._update_render_card(media, timeline)

    def _refresh_summary(self, media: list[dict[str, Any]], timeline: dict[str, Any] | None) -> None:
        for widget in self.summary_frame.winfo_children():
            widget.destroy()
        narration = next((item for item in media if item["media_type"] == "narration"), None)
        values = (("DURACAO", format_duration(narration.get("duration") if narration else None)), ("VIDEOS", str(sum(item["media_type"] == "video" for item in media))), ("IMAGENS", str(sum(item["media_type"] == "image" for item in media))), ("TIMELINE", f"{len(timeline['segments'])} segmentos" if timeline else "Pendente"))
        for index, (label, value) in enumerate(values):
            card = ctk.CTkFrame(self.summary_frame, fg_color=theme.CARD, corner_radius=theme.SMALL_RADIUS)
            card.grid(row=0, column=index, padx=(0 if index == 0 else 5, 5 if index < 3 else 0), sticky="ew")
            ctk.CTkLabel(card, text=label, text_color=theme.TEXT_MUTED, font=theme.FONT_SMALL).pack(anchor="w", padx=14, pady=(12, 2))
            ctk.CTkLabel(card, text=value, text_color=theme.TEXT_PRIMARY, font=(theme.FONT_FAMILY, 17, "bold")).pack(anchor="w", padx=14, pady=(0, 12))

    def _refresh_media_cards(self, media: list[dict[str, Any]]) -> None:
        for widget in self.media_summary.winfo_children():
            widget.destroy()
        for widget in self.media_expand_frame.winfo_children():
            widget.destroy()
        grouped = {kind: [item for item in media if item["media_type"] == kind] for kind in ("video", "image", "narration", "music")}
        labels = {"video": "Videos", "image": "Imagens", "narration": "Narracao", "music": "Musica"}
        for index, kind in enumerate(grouped):
            items = grouped[kind]
            card = ctk.CTkFrame(self.media_summary, fg_color=theme.CARD, corner_radius=theme.SMALL_RADIUS)
            card.grid(row=0, column=index, padx=(0 if index == 0 else 5, 5 if index < 3 else 0), sticky="ew")
            ctk.CTkLabel(card, text=labels[kind], text_color=theme.TEXT_PRIMARY, font=theme.FONT_SECTION).pack(anchor="w", padx=14, pady=(12, 2))
            detail = f"{len(items)} arquivo(s)" if kind in ("video", "image") else (items[0]["original_name"] if items else "Nenhuma")
            ctk.CTkLabel(card, text=detail, text_color=theme.TEXT_SECONDARY, font=theme.FONT_SMALL, wraplength=180).pack(anchor="w", padx=14, pady=(0, 6))
            ctk.CTkButton(card, text="Adicionar" if kind in ("video", "image") else "Alterar", command=lambda media_type=kind: self._select_many(media_type) if media_type in ("video", "image") else self._select_one(media_type), width=86, height=27, fg_color=theme.SURFACE, hover_color=theme.CARD_HOVER, text_color=theme.TEXT_SECONDARY).pack(anchor="w", padx=14, pady=(0, 12))
        if self.media_expanded:
            self.media_expand_frame.pack(fill="x", padx=14, pady=(0, 4))
            for kind, items in grouped.items():
                for item in items:
                    ctk.CTkLabel(self.media_expand_frame, text=f"{item['original_name']}   •   {self._media_description(item)}", text_color=theme.TEXT_SECONDARY, font=theme.FONT_SMALL, anchor="w").pack(fill="x", pady=2)

    def toggle_media(self) -> None:
        self.media_expanded = not self.media_expanded
        if self.media_expanded:
            self.media_expand_button.configure(text="Ocultar arquivos")
        else:
            self.media_expand_button.configure(text="Ver arquivos")
        self.refresh_media()

    def _refresh_timeline(self, timeline: dict[str, Any] | None, media: list[dict[str, Any]]) -> None:
        for widget in self.timeline_frame.winfo_children():
            widget.destroy()
        if not timeline:
            ctk.CTkLabel(self.timeline_frame, text="Nenhuma timeline gerada ainda.", text_color=theme.TEXT_MUTED, font=theme.FONT_BODY).pack(anchor="w", padx=8, pady=10)
            self.timeline_toggle.pack_forget()
            return
        media_by_id = {item["id"]: item for item in media}
        segments = timeline["segments"] if self.timeline_expanded else timeline["segments"][:5]
        for segment in segments:
            item = media_by_id.get(segment["media_id"], {})
            row = ctk.CTkFrame(self.timeline_frame, fg_color=theme.CARD, corner_radius=theme.SMALL_RADIUS)
            row.pack(fill="x", pady=3)
            kind = "VIDEO" if segment["media_type"] == "video" else "IMAGEM"
            ctk.CTkLabel(row, text=f"{format_duration(segment['timeline_start'])} → {format_duration(segment['timeline_end'])}", text_color=theme.TEXT_PRIMARY, font=theme.FONT_SECTION).pack(side="left", padx=12, pady=10)
            ctk.CTkLabel(row, text=kind, text_color=theme.PRIMARY if kind == "VIDEO" else theme.SUCCESS, font=theme.FONT_SMALL).pack(side="left", padx=12)
            ctk.CTkLabel(row, text=item.get("original_name", "Midia removida"), text_color=theme.TEXT_SECONDARY, font=theme.FONT_BODY).pack(side="left", padx=4)
        if len(timeline["segments"]) > 5:
            self.timeline_toggle.pack(anchor="w", padx=14, pady=(0, 12))
            self.timeline_toggle.configure(text="Ocultar timeline" if self.timeline_expanded else "Ver timeline completa")
        else:
            self.timeline_toggle.pack_forget()

    def toggle_timeline(self) -> None:
        self.timeline_expanded = not self.timeline_expanded
        self.refresh_media()

    def rename_project(self) -> None:
        window = self.winfo_toplevel()
        if hasattr(window, "rename_project"):
            window.rename_project(self.project["id"])

    def show_actions(self) -> None:
        window = self.winfo_toplevel()
        if hasattr(window, "show_project_menu"):
            window.show_project_menu(self.project["id"])

    def _refresh_scenes(self) -> None:
        for widget in self.scenes_frame.winfo_children():
            widget.destroy()
        scenes = self.project_manager.get_narrative_scenes(self.project["id"])
        ctk.CTkButton(self.scenes_frame, text="Criar Cenas de Teste", command=self.create_test_scenes, width=150, height=30, fg_color=theme.SURFACE, hover_color=theme.CARD_HOVER).pack(anchor="w", pady=(0, 8))
        if not scenes:
            ctk.CTkLabel(self.scenes_frame, text="Nenhuma analise narrativa disponivel.", text_color=theme.TEXT_MUTED, font=theme.FONT_SMALL).pack(anchor="w")
            return
        for scene in scenes:
            ctk.CTkLabel(self.scenes_frame, text=f"Cena {scene['scene_order']}  •  {format_duration(scene['start_time'])} - {format_duration(scene['end_time'])}  •  {scene['text']}  •  {scene['importance']:.0%}", text_color=theme.TEXT_SECONDARY, anchor="w", font=theme.FONT_SMALL).pack(fill="x", pady=2)

    def _update_flow(self, media: list[dict[str, Any]], timeline: dict[str, Any] | None) -> None:
        narration = any(item["media_type"] == "narration" for item in media)
        visuals = any(item["media_type"] in ("video", "image") for item in media)
        states = (visuals, narration, timeline is not None, False)
        for index, label in enumerate(self.step_labels):
            label.configure(text_color=theme.SUCCESS if states[index] else theme.PRIMARY if index == next((i for i, value in enumerate(states) if not value), 3) else theme.TEXT_MUTED)
        ready = visuals and narration and timeline is not None
        self.status_badge.configure(text="  Projeto pronto  " if ready else "  Configuracao incompleta  ", text_color=theme.SUCCESS if ready else theme.WARNING)

    def _update_render_card(self, media: list[dict[str, Any]], timeline: dict[str, Any] | None) -> None:
        narration = next((item for item in media if item["media_type"] == "narration"), None)
        music = next((item for item in media if item["media_type"] == "music"), None)
        if timeline:
            self.render_info.configure(text=f"Preset: Kids Story V1\nDuracao: {format_duration(timeline['duration'])}   •   Segmentos: {len(timeline['segments'])}   •   Musica: {'Ativada' if music else 'Nenhuma'}")
        else:
            self.render_info.configure(text="Gere uma timeline para preparar o preview.")
        self.render_button.configure(state="normal" if timeline and timeline.get("segments") else "disabled")

    def create_test_scenes(self) -> None:
        try:
            self.project_manager.create_test_scenes(self.project["id"])
            self.refresh_media()
        except (RuntimeError, ValueError, OSError) as error:
            messagebox.showerror("Nao foi possivel criar cenas", str(error), parent=self)

    def transcribe_narration(self) -> None:
        self._run_background("Transcrevendo narracao...", self.project_manager.transcribe_narration)

    def analyze_story(self) -> None:
        self._run_background("Analisando historia...", self.project_manager.analyze_story)

    def prepare_with_ai(self) -> None:
        self._run_background("Preparando com IA...", self.project_manager.prepare_with_ai)

    def _run_background(self, message: str, operation: Any) -> None:
        self.render_button.configure(state="disabled")
        self.render_status_label.configure(text=message, text_color=theme.TEXT_SECONDARY)

        def progress(percent: int, text: str) -> None:
            self.after(0, lambda: self._update_background_progress(percent, text))

        def worker() -> None:
            try:
                operation(self.project["id"], progress_callback=progress)
            except Exception as error:
                self.after(0, lambda: messagebox.showerror("Operação não concluída", str(error), parent=self))
            else:
                self.after(0, self._background_finished)

        threading.Thread(target=worker, daemon=True).start()

    def _update_background_progress(self, percent: int, text: str) -> None:
        self.progress_bar.set(percent / 100)
        self.render_status_label.configure(text=f"{percent}%  {text}")

    def _background_finished(self) -> None:
        self.progress_bar.set(1)
        self.render_status_label.configure(text="100%  Pronto", text_color=theme.SUCCESS)
        self.refresh_media()

    def generate_timeline(self) -> None:
        try:
            self.project_manager.generate_timeline(self.project["id"])
            self.refresh_media()
        except (RuntimeError, ValueError, OSError) as error:
            messagebox.showerror("Nao foi possivel gerar a timeline", str(error), parent=self)

    def render_preview(self) -> None:
        if not messagebox.askyesno("Gerar video", "Gerar video usando a timeline atual?", parent=self):
            return
        self.render_button.configure(state="disabled")
        self.progress_bar.set(0)
        self.render_status_label.configure(text="Renderizando video...", text_color=theme.TEXT_SECONDARY)
        self.update_idletasks()
        def update_progress(percent: int, message: str) -> None:
            self.progress_bar.set(percent / 100)
            self.render_status_label.configure(text=f"{percent}%  {message}")
            self.update_idletasks()
        try:
            render = self.project_manager.render_preview(self.project["id"], progress_callback=update_progress)
            self.last_output_path = Path(render["file_path"])
            self.render_status_label.configure(text="100%  Video pronto", text_color=theme.SUCCESS)
            for widget in self.result_frame.winfo_children():
                widget.destroy()
            ctk.CTkLabel(self.result_frame, text="✓  Video pronto", text_color=theme.SUCCESS, font=theme.FONT_SECTION).pack(side="left", padx=14, pady=12)
            ctk.CTkLabel(self.result_frame, text=self.last_output_path.name, text_color=theme.TEXT_SECONDARY, font=theme.FONT_SMALL).pack(side="left", padx=8)
            ctk.CTkButton(self.result_frame, text="Abrir video", command=self.open_video, width=94, height=28).pack(side="right", padx=6, pady=7)
            ctk.CTkButton(self.result_frame, text="Abrir pasta", command=self.open_output_folder, width=94, height=28, fg_color=theme.SURFACE, hover_color=theme.CARD_HOVER).pack(side="right", padx=6, pady=7)
            self.result_frame.grid()
        except (VideoRenderError, RuntimeError, OSError) as error:
            self.render_status_label.configure(text="Falha no render", text_color=theme.ERROR)
            messagebox.showerror("Erro ao gerar video", str(error), parent=self)
        finally:
            self._update_render_card(self.project_manager.list_project_media(self.project["id"]), self.project_manager.get_project_timeline(self.project["id"]))

    def open_video(self) -> None:
        if self.last_output_path and self.last_output_path.exists():
            os.startfile(str(self.last_output_path))

    def open_output_folder(self) -> None:
        if self.last_output_path and self.last_output_path.exists():
            os.startfile(str(self.last_output_path.parent))

    def _select_many(self, media_type: str) -> None:
        filters = {"video": ("Videos", "*.mp4 *.mov *.mkv *.avi *.webm"), "image": ("Imagens", "*.png *.jpg *.jpeg *.webp")}
        paths = filedialog.askopenfilenames(parent=self, title=f"Adicionar {media_type}", filetypes=[filters[media_type], ("Todos os arquivos", "*.*")])
        self._import_files(paths, media_type)

    def _select_one(self, media_type: str) -> None:
        path = filedialog.askopenfilename(parent=self, title=f"Alterar {media_type}", filetypes=[("Audio", "*.mp3 *.wav *.m4a *.aac"), ("Todos os arquivos", "*.*")])
        if path:
            self._import_files((path,), media_type)

    def _import_files(self, paths: tuple[str, ...], media_type: str) -> None:
        errors = []
        for path in paths:
            try:
                self.project_manager.import_media(self.project["id"], path, media_type)
            except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
                errors.append(f"{Path(path).name}: {error}")
        self.refresh_media()
        if errors:
            messagebox.showerror("Erro ao importar", "\n".join(errors), parent=self)

    @staticmethod
    def _media_description(media: dict[str, Any]) -> str:
        if media.get("probe_status") != "success":
            return "Metadados indisponiveis"
        if media["media_type"] == "video":
            return f"{format_duration(media.get('duration'))} • {media.get('width') or '?'}x{media.get('height') or '?'} • {media.get('fps') or '?'} FPS"
        if media["media_type"] == "image":
            return f"{media.get('width') or '?'}x{media.get('height') or '?'}"
        return format_duration(media.get("duration"))
