"""Main window for Campaign Suppression Manager."""

from __future__ import annotations

try:
    import customtkinter as ctk
except ModuleNotFoundError:  # pragma: no cover - fallback for local import checks
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    class _FallbackApp:
        """Lightweight fallback if CustomTkinter is not installed."""

        def __init__(self) -> None:
            self._root = tk.Tk()
            self._root.title("Campaign Suppression Manager")
            self._root.geometry("1000x700")
            self._root.minsize(900, 650)

            self._status = tk.StringVar(value="Ready")

            container = ttk.Frame(self._root, padding=16)
            container.pack(fill="both", expand=True)

            ttk.Label(container, text="Campaign Suppression Manager", font=("Segoe UI", 18, "bold")).pack(anchor="w")
            ttk.Label(container, text="CustomTkinter is not installed. This fallback keeps the app importable.").pack(anchor="w", pady=(8, 12))

            ttk.Button(container, text="Select Campaign Excel", command=self._select_excel).pack(anchor="w", pady=4)
            ttk.Button(container, text="Select ZIP Folder", command=self._select_zip_folder).pack(anchor="w", pady=4)
            ttk.Button(container, text="Select Output Folder", command=self._select_output_folder).pack(anchor="w", pady=4)

            self._root.grid_columnconfigure(0, weight=1)
            ttk.Label(container, textvariable=self._status).pack(anchor="w", pady=(12, 0))

        def _select_excel(self) -> None:
            filedialog.askopenfilename(title="Select Campaign Excel", filetypes=[("Excel files", "*.xlsx *.xlsm *.xls")])

        def _select_zip_folder(self) -> None:
            filedialog.askdirectory(title="Select ZIP Folder")

        def _select_output_folder(self) -> None:
            filedialog.askdirectory(title="Select Output Folder")

        def run(self) -> None:
            self._root.mainloop()


else:
    from pathlib import Path
    import os
    import threading
    from tkinter import filedialog, messagebox
    from typing import Callable, TypeVar

    from config.run_config import MappingConfig, RunConfig
    from config.user_settings import UserSettings, load_user_settings, save_user_settings
    from core.processor import CampaignSuppressionProcessor
    from models.mapping import MappingStrategy

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    ResultType = TypeVar("ResultType")

    class CampaignSuppressionApp(ctk.CTk):
        """Main application window for the Campaign Suppression Manager."""

        def __init__(self) -> None:
            super().__init__()
            self.title("Campaign Suppression Manager")
            self.geometry("1220x820")
            self.minsize(1080, 740)

            self._excel_path: Path | None = None
            self._zip_folder: Path | None = None
            self._output_folder: Path | None = None
            self._validation_report = None
            self._selected_strategy = ctk.StringVar(value=MappingStrategy.EXACT.value)
            self._pattern_template = ctk.StringVar(value="{campaign}")
            self._user_settings = load_user_settings()
            self._is_busy = False

            self._status_text = ctk.StringVar(value="Ready")
            self._build_layout()
            self._load_user_settings()
            self.protocol("WM_DELETE_WINDOW", self._on_close)

        def _build_layout(self) -> None:
            header = ctk.CTkFrame(self, corner_radius=16)
            header.pack(fill="x", padx=20, pady=(20, 12))

            ctk.CTkLabel(
                header,
                text="Campaign Suppression Manager",
                font=ctk.CTkFont(size=26, weight="bold"),
            ).pack(anchor="w", padx=18, pady=(18, 4))
            ctk.CTkLabel(
                header,
                text="Validate the campaign-to-ZIP mapping before extracting suppression files.",
                font=ctk.CTkFont(size=14),
            ).pack(anchor="w", padx=18, pady=(0, 18))

            top = ctk.CTkFrame(self, corner_radius=16)
            top.pack(fill="x", padx=20, pady=(0, 12))
            top.grid_columnconfigure(1, weight=1)

            self._excel_entry = self._create_path_row(top, 0, "Campaign Excel", self._browse_excel)
            self._zip_entry = self._create_path_row(top, 1, "ZIP Folder", self._browse_zip_folder)
            self._output_entry = self._create_path_row(top, 2, "Output Folder", self._browse_output_folder)
            self._mapping_row = self._create_mapping_row(top, 3)

            self._pattern_template_row = ctk.CTkFrame(top, fg_color="transparent")
            self._pattern_template_row.grid(row=4, column=0, columnspan=3, sticky="ew", padx=18, pady=(0, 12))
            self._pattern_template_row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(self._pattern_template_row, text="Pattern Template").grid(row=0, column=0, sticky="w", padx=(0, 12))
            self._pattern_template_entry = ctk.CTkEntry(self._pattern_template_row, textvariable=self._pattern_template)
            self._pattern_template_entry.grid(row=0, column=1, sticky="ew")
            ctk.CTkLabel(self._pattern_template_row, text="Use {campaign} as the campaign placeholder.", text_color=("gray30", "gray70")).grid(row=1, column=1, sticky="w", pady=(4, 0))
            self._pattern_template_row.grid_remove()

            actions = ctk.CTkFrame(self, corner_radius=16)
            actions.pack(fill="x", padx=20, pady=(0, 12))
            actions.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

            self._validate_button = ctk.CTkButton(actions, text="Validate", height=42, command=self._validate)
            self._validate_button.grid(row=0, column=0, sticky="ew", padx=18, pady=16)

            self._start_button = ctk.CTkButton(actions, text="Start", height=42, command=self._start, state="disabled")
            self._start_button.grid(row=0, column=1, sticky="ew", padx=18, pady=16)

            self._clear_button = ctk.CTkButton(actions, text="Clear", height=42, command=self._clear)
            self._clear_button.grid(row=0, column=2, sticky="ew", padx=18, pady=16)

            self._open_button = ctk.CTkButton(actions, text="Open Output Folder", height=42, command=self._open_output_folder)
            self._open_button.grid(row=0, column=3, sticky="ew", padx=18, pady=16)

            self._preview_button = ctk.CTkButton(actions, text="Preview Mapping", height=42, command=self._show_preview_only, state="disabled")
            self._preview_button.grid(row=0, column=4, sticky="ew", padx=18, pady=16)

            content = ctk.CTkFrame(self, corner_radius=16)
            content.pack(fill="both", expand=True, padx=20, pady=(0, 12))
            content.grid_columnconfigure(0, weight=1)
            content.grid_columnconfigure(1, weight=1)
            content.grid_rowconfigure(1, weight=1)

            ctk.CTkLabel(content, text="Preview / Validation", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, sticky="w", padx=18, pady=(16, 8))
            ctk.CTkLabel(content, text="Live Log", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=1, sticky="w", padx=18, pady=(16, 8))

            self._preview_text = ctk.CTkTextbox(content, wrap="word")
            self._preview_text.grid(row=1, column=0, sticky="nsew", padx=(18, 9), pady=(0, 16))

            self._log_text = ctk.CTkTextbox(content, wrap="word")
            self._log_text.grid(row=1, column=1, sticky="nsew", padx=(9, 18), pady=(0, 16))

            footer = ctk.CTkFrame(self, corner_radius=16)
            footer.pack(fill="x", padx=20, pady=(0, 20))

            self._progress = ctk.CTkProgressBar(footer)
            self._progress.set(0)
            self._progress.pack(fill="x", padx=18, pady=(16, 10))

            self._status_label = ctk.CTkLabel(footer, textvariable=self._status_text, anchor="w")
            self._status_label.pack(fill="x", padx=18, pady=(0, 16))

        def _create_path_row(self, parent: ctk.CTkFrame, row: int, label: str, command) -> ctk.CTkEntry:
            ctk.CTkLabel(parent, text=label).grid(row=row, column=0, sticky="w", padx=18, pady=12)
            entry = ctk.CTkEntry(parent)
            entry.grid(row=row, column=1, sticky="ew", padx=(0, 12), pady=12)
            ctk.CTkButton(parent, text="Browse", width=110, command=command).grid(row=row, column=2, sticky="e", padx=18, pady=12)
            return entry

        def _create_mapping_row(self, parent: ctk.CTkFrame, row: int) -> None:
            ctk.CTkLabel(parent, text="Mapping Strategy").grid(row=row, column=0, sticky="w", padx=18, pady=12)
            selector = ctk.CTkOptionMenu(
                parent,
                values=[strategy.value for strategy in MappingStrategy],
                variable=self._selected_strategy,
                command=self._handle_strategy_change,
            )
            selector.grid(row=row, column=1, sticky="w", padx=(0, 12), pady=12)
            ctk.CTkLabel(parent, text="Exact, partial, or pattern-based matching.", text_color=("gray30", "gray70")).grid(row=row, column=2, sticky="w", padx=18, pady=12)

        def _handle_strategy_change(self, selected_value: str) -> None:
            if selected_value == MappingStrategy.PATTERN.value:
                self._pattern_template_row.grid()
            else:
                self._pattern_template_row.grid_remove()
            self._persist_user_settings()

        def _browse_excel(self) -> None:
            file_path = filedialog.askopenfilename(title="Select Campaign Excel", filetypes=[("Excel files", "*.xlsx *.xlsm")])
            if file_path:
                self._excel_path = Path(file_path)
                self._set_entry(self._excel_entry, file_path)
                self._set_status(f"Selected campaign workbook: {self._excel_path.name}")
                self._persist_user_settings()

        def _browse_zip_folder(self) -> None:
            folder_path = filedialog.askdirectory(title="Select ZIP Folder")
            if folder_path:
                self._zip_folder = Path(folder_path)
                self._set_entry(self._zip_entry, folder_path)
                self._set_status(f"Selected ZIP folder: {self._zip_folder.name}")
                self._persist_user_settings()

        def _browse_output_folder(self) -> None:
            folder_path = filedialog.askdirectory(title="Select Output Folder")
            if folder_path:
                self._output_folder = Path(folder_path)
                self._set_entry(self._output_entry, folder_path)
                self._set_status(f"Selected output folder: {self._output_folder.name}")
                self._persist_user_settings()

        def _validate(self) -> None:
            processor = self._build_processor()
            if processor is None:
                return

            self._run_background_task(
                task_name="Validation",
                worker=processor.validate,
                on_success=self._handle_validation_result,
            )

        def _show_preview_only(self) -> None:
            if self._validation_report is None:
                messagebox.showinfo("Preview", "Run Validate first.")
                return
            self._show_preview_dialog(self._validation_report)

        def _start(self) -> None:
            if self._validation_report is None or self._validation_report.issues:
                messagebox.showerror("Start blocked", "Run a successful validation first.")
                return

            processor = self._build_processor()
            if processor is None:
                return

            self._run_background_task(
                task_name="Extraction",
                worker=lambda: processor.extract(self._validation_report),
                on_success=self._handle_extraction_result,
            )

        def _clear(self) -> None:
            if self._is_busy:
                messagebox.showinfo("Busy", "Wait for the current operation to finish.")
                return

            self._excel_path = None
            self._zip_folder = None
            self._output_folder = None
            self._validation_report = None
            self._set_entry(self._excel_entry, "")
            self._set_entry(self._zip_entry, "")
            self._set_entry(self._output_entry, "")
            self._set_preview_text("")
            self._set_log_text("")
            self._set_start_enabled(False)
            self._preview_button.configure(state="disabled")
            self._progress.set(0)
            self._set_status("Ready")

        def _open_output_folder(self) -> None:
            if self._output_folder is None or not self._output_folder.exists():
                messagebox.showinfo("Open Output Folder", "Select an output folder first.")
                return

            os.startfile(self._output_folder)  # type: ignore[attr-defined]

        def _build_processor(self):
            if self._excel_path is None or self._zip_folder is None or self._output_folder is None:
                messagebox.showerror("Missing input", "Select the campaign Excel, ZIP folder, and output folder first.")
                return None

            from config.run_config import MappingConfig, RunConfig
            from core.processor import CampaignSuppressionProcessor
            from models.mapping import MappingStrategy

            selected_strategy = MappingStrategy(self._selected_strategy.get())
            pattern_template = self._pattern_template.get().strip() or None
            if selected_strategy == MappingStrategy.PATTERN and not pattern_template:
                messagebox.showerror("Missing pattern template", "Provide a pattern template when using pattern mapping.")
                return None

            run_config = RunConfig(
                excel_path=self._excel_path,
                zip_folder=self._zip_folder,
                output_folder=self._output_folder,
                mapping=MappingConfig(strategy=selected_strategy, pattern_template=pattern_template),
            )
            self._persist_user_settings()
            return CampaignSuppressionProcessor(run_config)

        def _format_validation_report(self, validation_report) -> str:
            lines: list[str] = []
            for output_position, preview in enumerate(validation_report.preview_rows, start=1):
                if preview.issue is None and preview.selected_zip_path is not None:
                    lines.append(f"{output_position:03d}. {preview.campaign.name} -> {preview.selected_zip_path.name}")
                else:
                    lines.append(f"{output_position:03d}. {preview.campaign.name} -> ISSUE")
                    if preview.issue is not None:
                        lines.append(f"    {preview.issue.message}")

            if validation_report.issues:
                lines.append("")
                lines.append("Issues:")
                lines.extend(f"- {issue.subject}: {issue.message}" for issue in validation_report.issues)

            return "\n".join(lines) if lines else "No preview available."

        def _format_issues(self, issues) -> str:
            return "\n".join(f"- {issue.subject}: {issue.message}" for issue in issues)

        def _show_preview_dialog(self, validation_report) -> bool:
            dialog = ctk.CTkToplevel(self)
            dialog.title("Preview Mapping")
            dialog.geometry("900x650")
            dialog.transient(self)
            dialog.grab_set()

            ctk.CTkLabel(dialog, text="Review campaign -> ZIP mapping before extraction.", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=18, pady=(18, 8))
            preview_box = ctk.CTkTextbox(dialog, wrap="word")
            preview_box.pack(fill="both", expand=True, padx=18, pady=(0, 18))
            preview_box.insert("1.0", self._format_validation_report(validation_report))
            preview_box.configure(state="disabled")

            confirmed = {"value": False}

            button_row = ctk.CTkFrame(dialog)
            button_row.pack(fill="x", padx=18, pady=(0, 18))

            def _confirm() -> None:
                confirmed["value"] = True
                dialog.destroy()

            def _cancel() -> None:
                dialog.destroy()

            ctk.CTkButton(button_row, text="Confirm and Continue", command=_confirm).pack(side="right", padx=(8, 0))
            ctk.CTkButton(button_row, text="Cancel", command=_cancel).pack(side="right")

            self.wait_window(dialog)
            return confirmed["value"]

        def _set_entry(self, entry: ctk.CTkEntry, value: str) -> None:
            entry.delete(0, "end")
            entry.insert(0, value)

        def _set_preview_text(self, text: str) -> None:
            self._preview_text.configure(state="normal")
            self._preview_text.delete("1.0", "end")
            self._preview_text.insert("1.0", text)

        def _set_log_text(self, text: str) -> None:
            self._log_text.configure(state="normal")
            self._log_text.delete("1.0", "end")
            self._log_text.insert("1.0", text)

        def _append_log(self, text: str) -> None:
            current = self._log_text.get("1.0", "end").strip()
            updated = f"{current}\n{text}".strip() if current else text
            self._set_log_text(updated)

        def _set_status(self, text: str) -> None:
            self._status_text.set(text)

        def _set_start_enabled(self, enabled: bool) -> None:
            self._start_button.configure(state="normal" if enabled else "disabled")

        def _set_busy(self, is_busy: bool, status_text: str | None = None) -> None:
            self._is_busy = is_busy
            state = "disabled" if is_busy else "normal"
            self._validate_button.configure(state=state)
            self._clear_button.configure(state=state)
            self._open_button.configure(state=state)
            self._preview_button.configure(state="disabled" if is_busy else self._preview_button.cget("state"))
            if not is_busy and self._validation_report is not None and not self._validation_report.issues:
                self._start_button.configure(state="normal")
            elif is_busy:
                self._start_button.configure(state="disabled")

            if status_text is not None:
                self._set_status(status_text)

        def _run_background_task(
            self,
            task_name: str,
            worker: Callable[[], ResultType],
            on_success: Callable[[ResultType], None],
        ) -> None:
            if self._is_busy:
                messagebox.showinfo("Busy", "Wait for the current operation to finish.")
                return

            self._set_busy(True, f"{task_name} in progress...")
            self._append_log(f"Starting {task_name.lower()}")
            self._progress.set(0.3)

            def _worker() -> None:
                try:
                    result = worker()
                except Exception as exc:  # pragma: no cover - defensive GUI boundary
                    self.after(0, lambda: self._handle_background_error(task_name, exc))
                    return

                self.after(0, lambda: self._handle_background_success(task_name, result, on_success))

            threading.Thread(target=_worker, daemon=True).start()

        def _handle_background_success(self, task_name: str, result, on_success: Callable[[object], None]) -> None:
            self._set_busy(False)
            on_success(result)

        def _handle_background_error(self, task_name: str, exc: Exception) -> None:
            self._set_busy(False)
            self._progress.set(0)
            self._append_log(f"{task_name} failed: {exc}")
            self._set_status(f"{task_name} failed")
            messagebox.showerror(f"{task_name} failed", str(exc))

        def _handle_validation_result(self, validation_report) -> None:
            self._validation_report = validation_report
            self._set_preview_text(self._format_validation_report(validation_report))
            self._preview_button.configure(state="normal")

            if validation_report.issues:
                self._set_status("Validation failed")
                self._set_start_enabled(False)
                self._append_log("Validation failed; extraction blocked")
                messagebox.showerror("Validation failed", self._format_issues(validation_report.issues))
                self._progress.set(0)
                return

            if self._show_preview_dialog(validation_report):
                self._set_status("Validation succeeded")
                self._set_start_enabled(True)
                self._append_log("Preview confirmed")
                self._progress.set(0.6)
            else:
                self._set_status("Preview canceled")
                self._set_start_enabled(False)
                self._append_log("Preview canceled by user")
                self._progress.set(0)

        def _handle_extraction_result(self, result) -> None:
            self._progress.set(1)
            self._set_status(f"Complete. Files written to {result.report_file.parent}")
            self._append_log(f"Extraction complete: {len(result.output_files)} files")
            messagebox.showinfo("Success", f"Extraction complete.\n\nOutput: {result.report_file.parent}")

        def _load_user_settings(self) -> None:
            settings = self._user_settings
            if settings.excel_path:
                self._excel_path = Path(settings.excel_path)
                self._set_entry(self._excel_entry, settings.excel_path)
            if settings.zip_folder:
                self._zip_folder = Path(settings.zip_folder)
                self._set_entry(self._zip_entry, settings.zip_folder)
            if settings.output_folder:
                self._output_folder = Path(settings.output_folder)
                self._set_entry(self._output_entry, settings.output_folder)

            available_strategies = {strategy.value for strategy in MappingStrategy}
            if settings.mapping_strategy in available_strategies:
                self._selected_strategy.set(settings.mapping_strategy)
            self._pattern_template.set(settings.pattern_template or "{campaign}")
            self._handle_strategy_change(self._selected_strategy.get())

        def _persist_user_settings(self) -> None:
            settings = UserSettings(
                excel_path=str(self._excel_path or ""),
                zip_folder=str(self._zip_folder or ""),
                output_folder=str(self._output_folder or ""),
                mapping_strategy=self._selected_strategy.get(),
                pattern_template=self._pattern_template.get().strip() or "{campaign}",
            )
            try:
                save_user_settings(settings)
            except OSError:
                self._append_log("Warning: could not save user settings.")

        def _on_close(self) -> None:
            self._persist_user_settings()
            self.destroy()

        def run(self) -> None:
            self.mainloop()


    class _FallbackApp:  # pragma: no cover - only used when CustomTkinter is not installed
        pass


CampaignSuppressionApp = CampaignSuppressionApp if "CampaignSuppressionApp" in globals() else _FallbackApp
