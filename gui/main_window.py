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
            self._root.title("ERA-Campaign Suppression Manager")
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
    from models.run import CampaignMappingPreview, ValidationReport
    from services.mapping_history import load_mapping_history, merge_mapping_history, save_mapping_history

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    ResultType = TypeVar("ResultType")

    class CampaignSuppressionApp(ctk.CTk):
        """Main application window for the Campaign Suppression Manager."""

        def __init__(self) -> None:
            super().__init__()
            self.title("ERA-Campaign Suppression Manager")
            self.geometry("1220x820")
            self.minsize(1080, 740)
            self.configure(fg_color=("#f3f7ff", "#0b1220"))

            self._excel_path: Path | None = None
            self._zip_folder: Path | None = None
            self._output_folder: Path | None = None
            self._validation_report = None
            self._selected_strategy = ctk.StringVar(value=MappingStrategy.AUTO.value)
            self._pattern_template = ctk.StringVar(value="{campaign}")
            self._user_settings = load_user_settings()
            self._is_busy = False

            self._status_text = ctk.StringVar(value="Ready")
            self._build_layout()
            self._load_user_settings()
            self.protocol("WM_DELETE_WINDOW", self._on_close)

        def _build_layout(self) -> None:
            self.grid_columnconfigure(0, weight=1)
            self.grid_rowconfigure(0, weight=1)

            self._scroll_frame = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
            self._scroll_frame.grid(row=0, column=0, sticky="nsew")
            self._scroll_frame.grid_columnconfigure(0, weight=1)

            container = ctk.CTkFrame(self._scroll_frame, fg_color="transparent")
            container.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
            container.grid_columnconfigure(0, weight=1)
            container.grid_rowconfigure(4, weight=1)

            header = ctk.CTkFrame(container, corner_radius=24, border_width=1, fg_color=("#f8fbff", "#162132"))
            header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
            header.grid_columnconfigure(0, weight=1)
            header.grid_columnconfigure(1, weight=0)

            accent_bar = ctk.CTkFrame(header, height=4, corner_radius=999, fg_color=("#2563eb", "#3b82f6"))
            accent_bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=18, pady=(18, 0))

            left = ctk.CTkFrame(header, fg_color="transparent")
            left.grid(row=1, column=0, sticky="w", padx=20, pady=18)
            ctk.CTkLabel(left, text="ERA-Campaign Suppression Manager", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w")
            ctk.CTkLabel(left, text="Precision campaign mapping, preview-first extraction, and elegant workflow automation.", font=ctk.CTkFont(size=13), text_color=("gray50", "gray70")).pack(anchor="w", pady=(6, 10))
            self._build_header_badges(left)

            right = ctk.CTkFrame(header, corner_radius=20, border_width=1, fg_color=("#eef7ff", "#1f2b3d"))
            right.grid(row=1, column=1, sticky="e", padx=18, pady=18)
            ctk.CTkLabel(right, text="Confidence-first flow", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=14, pady=(12, 4))
            ctk.CTkLabel(right, text="Auto-match • Preview • Extract", font=ctk.CTkFont(size=12), text_color=("gray50", "gray70")).pack(anchor="w", padx=14, pady=(0, 12))

            input_card = self._create_section_card(container, 1, "Get started", "Select your campaign source, ZIP folder, and output destination.")
            self._excel_entry = self._create_path_card(input_card, 0, "Campaign Excel", "Workbook with the campaign names.", self._browse_excel)
            self._zip_entry = self._create_path_card(input_card, 1, "ZIP Folder", "Folder containing the downloaded ZIP archives.", self._browse_zip_folder)
            self._output_entry = self._create_path_card(input_card, 2, "Output Folder", "Destination for extracted suppression files.", self._browse_output_folder)

            actions_card = self._create_section_card(container, 2, "Workflow", "Run validation, inspect the preview, and extract with confidence.")
            actions_card.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

            self._validate_button = ctk.CTkButton(actions_card, text="Validate", height=46, command=self._validate, corner_radius=14, fg_color=("#2563eb", "#3b82f6"), hover_color=("#1d4ed8", "#60a5fa"))
            self._validate_button.grid(row=0, column=0, sticky="ew", padx=8, pady=14)

            self._start_button = ctk.CTkButton(actions_card, text="Extract", height=46, command=self._start, state="disabled", corner_radius=14, fg_color=("#0f766e", "#14b8a6"), hover_color=("#115e59", "#2dd4bf"))
            self._start_button.grid(row=0, column=1, sticky="ew", padx=8, pady=14)

            self._preview_button = ctk.CTkButton(actions_card, text="Preview", height=46, command=self._show_preview_only, state="disabled", corner_radius=14, fg_color=("#7c3aed", "#8b5cf6"), hover_color=("#6d28d9", "#a78bfa"))
            self._preview_button.grid(row=0, column=2, sticky="ew", padx=8, pady=14)

            self._clear_button = ctk.CTkButton(actions_card, text="Clear", height=46, command=self._clear, corner_radius=14, fg_color=("#475569", "#64748b"), hover_color=("#334155", "#94a3b8"))
            self._clear_button.grid(row=0, column=3, sticky="ew", padx=8, pady=14)

            self._open_button = ctk.CTkButton(actions_card, text="Open Output", height=46, command=self._open_output_folder, corner_radius=14, fg_color=("#1f2937", "#374151"), hover_color=("#111827", "#4b5563"))
            self._open_button.grid(row=0, column=4, sticky="ew", padx=8, pady=14)

            summary_card = self._create_section_card(container, 3, "Summary", "Essential status and mapping preview for your current run.")
            summary_card.grid_columnconfigure(0, weight=1)
            self._preview_text = self._create_panel(summary_card, 0, "Preview / Validation", "Review resolved campaign → ZIP mappings and issue highlights.")
            self._status_label = ctk.CTkLabel(summary_card, textvariable=self._status_text, anchor="w", font=ctk.CTkFont(size=12, weight="bold"), text_color=("#0f172a", "#475569"))
            self._status_label.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 8))
            self._progress = ctk.CTkProgressBar(summary_card, height=14, corner_radius=999)
            self._progress.set(0)
            self._progress.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 18))

            advanced_card = self._create_section_card(container, 4, "Advanced", "Open advanced diagnostics and expert settings.")
            toggle_row = ctk.CTkFrame(advanced_card, fg_color="transparent")
            toggle_row.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 12))
            toggle_row.grid_columnconfigure(0, weight=1)
            self._advanced_toggle_button = ctk.CTkButton(toggle_row, text="Show advanced details", command=self._toggle_advanced_details, corner_radius=14, fg_color=("#e2e8f0", "#334155"), hover_color=("#cbd5e1", "#475569"), text_color=("#0f172a", "#f8fafc"))
            self._advanced_toggle_button.grid(row=0, column=0, sticky="w")

            self._advanced_frame = ctk.CTkFrame(advanced_card, corner_radius=16, fg_color=("#ffffff", "#141e2f"))
            self._advanced_frame.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 16))
            self._advanced_frame.grid_columnconfigure(0, weight=1)
            self._advanced_frame.grid_rowconfigure(0, weight=1)
            self._advanced_frame.grid_remove()

            self._advanced_tabs = ctk.CTkTabview(self._advanced_frame, width=1080, height=280, corner_radius=16)
            self._advanced_tabs.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
            self._advanced_tabs.add("Logs")
            self._advanced_tabs.add("Settings")
            self._advanced_tabs.tab("Logs").grid_columnconfigure(0, weight=1)
            self._advanced_tabs.tab("Logs").grid_rowconfigure(0, weight=1)
            self._log_text = ctk.CTkTextbox(self._advanced_tabs.tab("Logs"), wrap="word", corner_radius=14, border_width=1, font=ctk.CTkFont(size=12), fg_color=("#f8fafc", "#111827"), text_color=("#0f172a", "#e2e8f0"))
            self._log_text.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)

            settings_tab = self._advanced_tabs.tab("Settings")
            settings_tab.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(settings_tab, text="Mapping Strategy", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="w", padx=18, pady=(18, 6))
            self._strategy_menu = ctk.CTkOptionMenu(settings_tab, values=[strategy.value for strategy in MappingStrategy], variable=self._selected_strategy, command=self._handle_strategy_change, width=240)
            self._strategy_menu.grid(row=1, column=0, sticky="w", padx=18, pady=(0, 14))
            ctk.CTkLabel(settings_tab, text="Pattern Template", font=ctk.CTkFont(size=13, weight="bold")).grid(row=2, column=0, sticky="w", padx=18, pady=(12, 6))
            self._pattern_entry = ctk.CTkEntry(settings_tab, textvariable=self._pattern_template, height=38, border_width=1, corner_radius=12, fg_color=("#f8fafc", "#0f172a"), text_color=("#0f172a", "#e2e8f0"))
            self._pattern_entry.grid(row=3, column=0, sticky="w", padx=18, pady=(0, 16))

        def _build_header_badges(self, parent: ctk.CTkFrame) -> None:
            badges = ["Auto-learning", "Alias-aware", "Preview-first"]
            for index, badge in enumerate(badges):
                badge_frame = ctk.CTkFrame(parent, corner_radius=999, border_width=1, fg_color=("#eff6ff", "#243447"))
                badge_frame.pack(anchor="w", pady=2)
                ctk.CTkLabel(badge_frame, text=badge, font=ctk.CTkFont(size=11, weight="bold"), text_color=("#2563eb", "#9fd6ff")).pack(padx=10, pady=6)

        def _create_section_card(self, parent: ctk.CTkFrame, row: int, title: str, subtitle: str) -> ctk.CTkFrame:
            card = ctk.CTkFrame(parent, corner_radius=24, border_width=1, fg_color=("#ffffff", "#0f172a"))
            card.grid(row=row, column=0, sticky="ew", padx=16, pady=8)
            card.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=18, weight="bold"), text_color=("#0f172a", "#e2e8f0")).grid(row=0, column=0, sticky="w", padx=18, pady=(18, 4))
            ctk.CTkLabel(card, text=subtitle, font=ctk.CTkFont(size=12), text_color=("#475569", "#94a3b8")).grid(row=1, column=0, sticky="w", padx=18, pady=(0, 16))
            return card

        def _create_path_card(self, parent: ctk.CTkFrame, row: int, label: str, hint: str, command) -> ctk.CTkEntry:
            card = ctk.CTkFrame(parent, corner_radius=20, border_width=1, fg_color=("#f8fafc", "#111827"))
            card.grid(row=row, column=0, sticky="ew", padx=10, pady=10)
            card.grid_columnconfigure(0, weight=1)
            card.grid_columnconfigure(1, weight=0)

            ctk.CTkLabel(card, text=label, font=ctk.CTkFont(size=13, weight="bold"), text_color=("#0f172a", "#e2e8f0")).grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 4))
            ctk.CTkLabel(card, text=hint, font=ctk.CTkFont(size=11), text_color=("#475569", "#94a3b8")).grid(row=1, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 14))

            entry = ctk.CTkEntry(card, height=44, border_width=1, corner_radius=14, fg_color=("#f8fafc", "#111827"), text_color=("#0f172a", "#e2e8f0"))
            entry.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))
            ctk.CTkButton(card, text="Browse", width=120, height=40, command=command, corner_radius=14, fg_color=("#2563eb", "#3b82f6"), hover_color=("#1d4ed8", "#60a5fa")).grid(row=2, column=1, sticky="e", padx=(12, 16), pady=(0, 16))
            return entry

        def _create_panel(self, parent: ctk.CTkFrame, column: int, title: str, hint: str) -> ctk.CTkTextbox:
            panel = ctk.CTkFrame(parent, corner_radius=20, border_width=1, fg_color=("#f8fafc", "#111827"))
            panel.grid(row=0, column=column, sticky="nsew", padx=(18, 9) if column == 0 else (9, 18), pady=18)
            panel.grid_columnconfigure(0, weight=1)
            panel.grid_rowconfigure(1, weight=1)
            ctk.CTkLabel(panel, text=title, font=ctk.CTkFont(size=15, weight="bold"), text_color=("#0f172a", "#e2e8f0")).grid(row=0, column=0, sticky="w", padx=18, pady=(18, 4))
            ctk.CTkLabel(panel, text=hint, font=ctk.CTkFont(size=11), text_color=("#475569", "#94a3b8")).grid(row=1, column=0, sticky="w", padx=18, pady=(0, 12))
            textbox = ctk.CTkTextbox(panel, wrap="word", corner_radius=16, border_width=1, font=ctk.CTkFont(size=12), fg_color=("#eff6ff", "#0f172a"), text_color=("#0f172a", "#e2e8f0"))
            textbox.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 18))
            return textbox

        def _handle_strategy_change(self, selected_value: str) -> None:
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

            if self._show_preview_dialog(self._validation_report):
                self._set_status("Preview confirmed")
                self._set_start_enabled(not self._validation_report.issues)
                self._append_log("Preview confirmed")
            else:
                self._set_status("Preview canceled")
                self._set_start_enabled(False)
                self._append_log("Preview canceled by user")

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

            pattern_template = self._pattern_template.get().strip() or None
            selected_strategy = MappingStrategy(self._selected_strategy.get()) if self._selected_strategy.get() in {strategy.value for strategy in MappingStrategy} else MappingStrategy.AUTO

            run_config = RunConfig(
                excel_path=self._excel_path,
                zip_folder=self._zip_folder,
                output_folder=self._output_folder,
                mapping=MappingConfig(strategy=selected_strategy, pattern_template=pattern_template),
            )
            self._persist_user_settings()
            return CampaignSuppressionProcessor(run_config)

        def _format_confidence(self, score: int | None) -> str:
            if score is None:
                return ""
            normalized = max(0, min(100, int(score)))
            return f" (confidence {normalized}%)"

        def _format_validation_report(self, validation_report) -> str:
            lines: list[str] = []
            for output_position, preview in enumerate(validation_report.preview_rows, start=1):
                if preview.issue is None and preview.selected_zip_path is not None:
                    confidence_text = self._format_confidence(preview.selected_score)
                    lines.append(f"{output_position:03d}. {preview.campaign.name} -> {preview.selected_zip_path.name}{confidence_text}")
                    if preview.warning:
                        lines.append(f"    WARNING: {preview.warning}")
                else:
                    lines.append(f"{output_position:03d}. {preview.campaign.name} -> ISSUE")
                    if preview.issue is not None:
                        lines.append(f"    {preview.issue.message}")

            if validation_report.warnings:
                lines.append("")
                lines.append("Warnings:")
                lines.extend(f"- {warning}" for warning in validation_report.warnings)

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
            dialog.geometry("960x720")
            dialog.transient(self)
            dialog.grab_set()

            ctk.CTkLabel(dialog, text="Review and adjust campaign -> ZIP mapping before extraction.", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=18, pady=(18, 8))
            ctk.CTkLabel(dialog, text="If any mapping looks wrong, choose the correct ZIP from the dropdown.", text_color=("gray30", "gray70")).pack(anchor="w", padx=18, pady=(0, 8))

            all_zip_paths = tuple(validation_report.available_zip_paths)
            zip_choices = [str(path) for path in all_zip_paths]
            if not zip_choices:
                zip_choices = [""]

            scroll_frame = ctk.CTkScrollableFrame(dialog, width=920, height=520, corner_radius=16)
            scroll_frame.pack(fill="both", expand=True, padx=18, pady=(0, 12))

            row_vars: list[tuple[CampaignMappingPreview, ctk.StringVar]] = []
            for preview in validation_report.preview_rows:
                row = ctk.CTkFrame(scroll_frame, corner_radius=12)
                row.pack(fill="x", pady=6, padx=8)
                row.grid_columnconfigure(1, weight=1)

                ctk.CTkLabel(row, text=preview.campaign.name, width=220, anchor="w").grid(row=0, column=0, sticky="w", padx=(12, 8), pady=8)
                selected_value = str(preview.selected_zip_path) if preview.selected_zip_path and str(preview.selected_zip_path) in zip_choices else zip_choices[0]
                selection_var = ctk.StringVar(value=selected_value)
                ctk.CTkOptionMenu(row, values=zip_choices, variable=selection_var, width=640).grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=8)

                issue_text = preview.issue.message if preview.issue is not None else ""
                ctk.CTkLabel(row, text=issue_text, text_color=("#ff5555", "#ff9999"), anchor="w").grid(row=1, column=0, columnspan=2, sticky="w", padx=(12, 12), pady=(0, 10))
                row_vars.append((preview, selection_var))

            confirmed = {"value": False}

            def _validate_selection() -> bool:
                selected_values = [selection_var.get() for _, selection_var in row_vars]
                if any(not value.strip() for value in selected_values):
                    messagebox.showerror("Mapping validation", "Please select a ZIP file for every campaign.")
                    return False
                if len(set(selected_values)) != len(selected_values):
                    messagebox.showerror("Mapping validation", "Each campaign must map to a unique ZIP file.")
                    return False
                return True

            def _confirm() -> None:
                if not _validate_selection():
                    return

                selected_mapping = {preview.campaign.name: Path(selection_var.get()) for preview, selection_var in row_vars}
                non_mapping_issues = tuple(
                    issue
                    for issue in validation_report.issues
                    if not issue.message.startswith("Expected exactly one ZIP match")
                )
                updated_preview_rows = []
                for preview, _ in row_vars:
                    selected_path = selected_mapping[preview.campaign.name]
                    selected_score = 0
                    for candidate in preview.candidate_scores:
                        if candidate.zip_path == selected_path:
                            selected_score = candidate.score
                            break

                    updated_preview_rows.append(
                        CampaignMappingPreview(
                            campaign=preview.campaign,
                            matched_zip_paths=preview.matched_zip_paths,
                            candidate_scores=preview.candidate_scores,
                            selected_zip_path=selected_path,
                            selected_score=selected_score,
                            warning=None,
                            issue=None,
                        )
                    )

                self._validation_report = ValidationReport(
                    preview_rows=tuple(updated_preview_rows),
                    campaign_count=validation_report.campaign_count,
                    zip_count=validation_report.zip_count,
                    missing_zip_count=0,
                    missing_suppression_count=validation_report.missing_suppression_count,
                    issues=non_mapping_issues,
                    warnings=validation_report.warnings,
                    available_zip_paths=validation_report.available_zip_paths,
                )
                self._set_preview_text(self._format_validation_report(self._validation_report))
                self._store_mapping_corrections({
                    preview.campaign.name: selected_mapping[preview.campaign.name].stem
                    for preview, _ in row_vars
                })
                self._set_status("Saved corrected mappings to memory")
                self._append_log("Saved corrected mappings to memory for future runs")
                confirmed["value"] = True
                dialog.destroy()

            def _cancel() -> None:
                dialog.destroy()

            button_row = ctk.CTkFrame(dialog)
            button_row.pack(fill="x", padx=18, pady=(0, 18))
            ctk.CTkButton(button_row, text="Confirm and Continue", command=_confirm).pack(side="right", padx=(8, 0))
            ctk.CTkButton(button_row, text="Cancel", command=_cancel).pack(side="right")

            self.wait_window(dialog)
            return confirmed["value"]

        def _set_entry(self, entry: ctk.CTkEntry, value: str) -> None:
            try:
                entry.configure(state="normal")
            except Exception:
                pass
            entry.delete(0, "end")
            entry.insert(0, value)
            try:
                entry.configure(state="readonly")
            except Exception:
                pass

        def _set_preview_text(self, text: str) -> None:
            self._preview_text.configure(state="normal")
            self._preview_text.delete("1.0", "end")
            self._preview_text.insert("1.0", text)

        def _store_mapping_corrections(self, corrections: dict[str, str]) -> None:
            try:
                existing_history = load_mapping_history()
                merged_history = merge_mapping_history(existing_history, corrections)
                save_mapping_history(merged_history)
            except Exception as error:
                messagebox.showwarning(
                    "Mapping history",
                    f"Could not save preview corrections to history: {error}",
                )

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

        def _toggle_advanced_details(self) -> None:
            if self._advanced_frame.winfo_ismapped():
                self._advanced_frame.grid_remove()
                self._advanced_toggle_button.configure(text="Show advanced details")
            else:
                self._advanced_frame.grid()
                self._advanced_toggle_button.configure(text="Hide advanced details")

        def _set_busy(self, is_busy: bool, status_text: str | None = None) -> None:
            self._is_busy = is_busy
            state = "disabled" if is_busy else "normal"
            self._validate_button.configure(state=state)
            self._clear_button.configure(state=state)
            self._open_button.configure(state=state)
            self._preview_button.configure(state="disabled" if is_busy else ("normal" if self._validation_report is not None else "disabled"))
            if is_busy:
                self._start_button.configure(state="disabled")
            elif self._validation_report is not None and not self._validation_report.issues:
                self._start_button.configure(state="normal")
            else:
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
            else:
                self._selected_strategy.set(MappingStrategy.AUTO.value)
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
