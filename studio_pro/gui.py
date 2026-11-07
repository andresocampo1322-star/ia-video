"""Interfaz nativa Tkinter: guion -> validación -> producción local.

Convive con la interfaz Stickman IA; no la altera. El botón de render solo
ejecuta modelos cuando el usuario lo solicita expresamente.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .production import produce


class StudioProUI(tk.Tk):
    BG = "#151923"
    FG = "#E9EDF5"
    MID = "#222A39"
    ACCENT = "#57C9BD"

    def __init__(self) -> None:
        super().__init__()
        self.title("ia-video | Studio Pro — producción de episodios")
        self.geometry("1020x780")
        self.minsize(820, 620)
        self.configure(bg=self.BG)
        self.queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.busy = False
        self._style()
        self._layout()
        self.after(200, self._drain)

    def _style(self) -> None:
        theme = ttk.Style(self)
        theme.theme_use("clam")
        theme.configure("Studio.TFrame", background=self.BG)
        theme.configure("Studio.TLabel", foreground=self.FG, background=self.BG,
                        font=("Segoe UI", 10))
        theme.configure("Header.TLabel", foreground=self.FG, background=self.BG,
                        font=("Segoe UI Semibold", 18))
        theme.configure("Studio.TEntry", fieldbackground=self.MID,
                        foreground=self.FG, insertcolor=self.FG, borderwidth=1)
        theme.configure("Studio.TButton", font=("Segoe UI Semibold", 10),
                        foreground="#102027", background=self.ACCENT, padding=8)
        theme.map("Studio.TButton", background=[("active", "#7CDED5")])
        theme.configure("Secondary.TButton", foreground=self.FG,
                        background="#3A4559", padding=8)
        theme.configure("Studio.Horizontal.TProgressbar", troughcolor=self.MID,
                        background=self.ACCENT)

    def _layout(self) -> None:
        frame = ttk.Frame(self, style="Studio.TFrame", padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="STUDIO PRO  •  LIBRETO A VIDEO",
                  style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            frame, style="Studio.TLabel",
            text="Modo original: genera MP4 con Stickman + Piper, sin ComfyUI. Modo neuronal: experimental."
        ).pack(anchor="w", pady=(3, 12))
        self.mode = tk.StringVar(value="original")
        modes = ttk.Frame(frame, style="Studio.TFrame")
        modes.pack(fill="x", pady=(0, 10))
        for caption, value in (
            ("Motor original Stickman IA 2D — sin configuración", "original"),
            ("Motor neuronal Pro — requiere ComfyUI", "neural"),
        ):
            button = tk.Radiobutton(
                modes, text=caption, variable=self.mode, value=value,
                bg=self.BG, fg=self.FG, selectcolor=self.MID,
                activebackground=self.BG, activeforeground=self.ACCENT,
                font=("Segoe UI", 10))
            button.pack(anchor="w")

        top = ttk.Frame(frame, style="Studio.TFrame")
        top.pack(fill="x")
        self.config_path = tk.StringVar()
        self.cast_path = tk.StringVar()
        self.output_path = tk.StringVar(value=str(Path.home() / "Videos" / "ia-video" / "episodio_01"))
        for caption, var, kind in (
            ("Configuración de modelos (solo Pro)", self.config_path, "file"),
            ("Biblia de personajes JSON (opcional)", self.cast_path, "file"),
            ("Carpeta del proyecto y MP4", self.output_path, "dir"),
        ):
            row = ttk.Frame(top, style="Studio.TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=caption, style="Studio.TLabel", width=37).pack(side="left")
            ttk.Entry(row, textvariable=var, style="Studio.TEntry").pack(
                side="left", fill="x", expand=True, padx=6)
            ttk.Button(row, text="Examinar...", style="Secondary.TButton",
                       command=lambda v=var, k=kind: self._browse(v, k)).pack(side="right")

        ttk.Label(frame, text="Libreto (texto completo)", style="Studio.TLabel").pack(
            anchor="w", pady=(18, 6))
        self.editor = tk.Text(frame, wrap="word", bg=self.MID, fg=self.FG,
                              insertbackground=self.FG, selectbackground="#385A6B",
                              font=("Segoe UI", 11), relief="flat", padx=12, pady=10,
                              height=11, undo=True)
        self.editor.pack(fill="both", expand=True)
        self.editor.insert("1.0",
                           "Un joven de cabello largo ve una alerta de emergencia en la televisión.\\n\\n"
                           "Abre la nevera: no tiene comida.\\n\\n"
                           "La vecina pálida le abre la puerta y comienza a sangrar por la nariz.\\n\\n"
                           "La vecina lo ataca y el joven huye, salta dos cercas y logra escapar.")
        buttons = ttk.Frame(frame, style="Studio.TFrame")
        buttons.pack(fill="x", pady=(12, 8))
        self.demo_button = ttk.Button(
            buttons, text="Cargar historia zombi", style="Secondary.TButton",
            command=self._load_demo)
        self.demo_button.pack(side="left", padx=(0, 7))
        self.check_button = ttk.Button(
            buttons, text="1. VALIDAR GUIÓN", style="Secondary.TButton",
            command=lambda: self._start(False))
        self.check_button.pack(side="left", padx=(0, 7))
        self.go_button = ttk.Button(
            buttons, text="2. GENERAR EPISODIO MP4", style="Studio.TButton",
            command=lambda: self._start(True))
        self.go_button.pack(side="left")
        ttk.Button(buttons, text="Abrir carpeta", style="Secondary.TButton",
                   command=self._open_folder).pack(side="right")

        self.status = tk.StringVar(value="Listo. Configura tus modelos una vez y escribe el libreto.")
        ttk.Label(frame, textvariable=self.status, style="Studio.TLabel").pack(anchor="w")
        self.progress = ttk.Progressbar(frame, style="Studio.Horizontal.TProgressbar",
                                        orient="horizontal", mode="indeterminate")
        self.progress.pack(fill="x", pady=(7, 9))
        self.log = tk.Text(frame, bg="#101620", fg="#BACADB", font=("Consolas", 9),
                           height=8, relief="flat", wrap="word", state="disabled")
        self.log.pack(fill="x")
        self._log("Motor original: animación vectorial 2D del repositorio, voz Piper y MP4 real.")
        self._log("Motor Pro: pendiente de modelos generativos reales; no promete anime sin GPU.")

    def _load_demo(self) -> None:
        root = Path(__file__).resolve().parents[1] / "examples" / "la_vecina"
        story = root / "historia.txt"
        cast = root / "personajes.json"
        if not story.is_file() or not cast.is_file():
            messagebox.showerror("Ejemplo no disponible", str(root))
            return
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", story.read_text(encoding="utf-8"))
        self.cast_path.set(str(cast))
        self._log("Cargada 'La vecina': guion y personajes preparados.")
        self.status.set("Historia zombi cargada. Puedes validar o generar el MP4 con Stickman IA.")

    def _browse(self, var: tk.StringVar, kind: str) -> None:
        if kind == "dir":
            selected = filedialog.askdirectory(title="Selecciona la carpeta del episodio")
        else:
            selected = filedialog.askopenfilename(
                title="Selecciona JSON de configuración o personajes",
                filetypes=[("Archivos JSON", "*.json"), ("Todos", "*.*")])
        if selected:
            var.set(selected)

    def _log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _open_folder(self) -> None:
        folder = Path(self.output_path.get()).expanduser()
        if not folder.is_dir():
            messagebox.showerror("Carpeta no encontrada", str(folder))
            return
        if sys.platform == "win32":
            os.startfile(str(folder))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])

    def _start(self, execute: bool) -> None:
        if self.busy:
            return
        content = self.editor.get("1.0", "end").strip()
        if not content:
            messagebox.showwarning("Falta libreto", "Escribe una historia primero.")
            return
        mode = self.mode.get()
        config = Path(self.config_path.get().strip()).expanduser()
        if mode == "neural" and not config.is_file():
            messagebox.showwarning(
                "Faltan modelos", "Para el modo neuronal selecciona un JSON de ComfyUI real. "
                "Para generar ahora sin ComfyUI selecciona Motor original Stickman IA.")
            return
        cast_value = self.cast_path.get().strip()
        if cast_value and not Path(cast_value).is_file():
            messagebox.showwarning("Biblia no encontrada", cast_value)
            return
        out = Path(self.output_path.get().strip()).expanduser()
        if not str(out).strip():
            return
        if execute and mode == "neural" and not messagebox.askyesno(
            "Confirmar generación real",
            "¿Ejecutar modelos ComfyUI para crear imágenes y videos?\n"
            "Esto puede consumir bastante GPU, electricidad o créditos "
            "si tu workflow utiliza servicios comerciales."):
            return
        out.mkdir(parents=True, exist_ok=True)
        script_file = out / "libreto_produccion.txt"
        script_file.write_text(content, encoding="utf-8")
        self.busy = True
        self.check_button.configure(state="disabled")
        self.go_button.configure(state="disabled")
        self.status.set("Procesando..." if execute else "Validando configuración...")
        self.progress.start(12)
        self._log(("Stickman IA original" if mode == "original" else "Motor neuronal Pro")
                  + " — " + ("RENDER MP4" if execute else "VALIDACIÓN") + " iniciado")
        def worker() -> None:
            try:
                if mode == "original":
                    from .original import render_original
                    def report(stage: str, fraction: float) -> None:
                        self.queue.put(("progress", f"{stage}: {fraction:.0%}"))
                    result = render_original(
                        content, out, cast_file=cast_value or None,
                        execute=execute,
                        log=lambda msg: self.queue.put(("log", str(msg))),
                        progress=report)
                else:
                    result = produce(
                        script_file, cast_value or None, config, out,
                        execute=execute, resume=True)
                self.queue.put(("success", json.dumps(result, ensure_ascii=False, indent=2)))
            except Exception as exc:
                self.queue.put(("error", f"{type(exc).__name__}: {exc}"))
        threading.Thread(target=worker, daemon=True).start()

    def _drain(self) -> None:
        try:
            while True:
                label, message = self.queue.get_nowait()
                if label == "progress":
                    self.status.set(message)
                    continue
                self._log(message)
                if label == "log":
                    continue
                if label == "success":
                    data = json.loads(message)
                    media = data.get("mp4") or data.get("episode")
                    if media and Path(media).is_file():
                        self.status.set("MP4 generado correctamente: " + str(media))
                        messagebox.showinfo("EPISODIO LISTO", f"Video generado en:\\n{media}")
                    elif data.get("status") == "validated" or data.get("executed") is False:
                        self.status.set("Guion validado; aún no se ha generado video.")
                    else:
                        self.status.set("Proceso finalizado. No se confirmó un archivo MP4.")
                else:
                    self.status.set("Error detectado — consulta el registro.")
                    messagebox.showerror("Producción interrumpida", message[:900])
                self.busy = False
                self.progress.stop()
                self.check_button.configure(state="normal")
                self.go_button.configure(state="normal")
        except queue.Empty:
            pass
        if self.busy and self.mode.get() == "neural":
            self._inspect_state()
        self.after(350, self._drain)

    def _inspect_state(self) -> None:
        file = Path(self.output_path.get()) / "production_state.json"
        if not file.is_file():
            return
        try:
            state = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        completed = sum(x.get("status") == "completed"
                        for x in state.get("shots", {}).values())
        refs = len(state.get("characters", {}))
        self.status.set(f"Estado: {state.get('status')} | "
                        f"{refs} referencias | {completed} planos completos")


def main() -> None:
    StudioProUI().mainloop()


if __name__ == "__main__":
    main()
