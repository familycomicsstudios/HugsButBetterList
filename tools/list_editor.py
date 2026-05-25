from __future__ import annotations

import json
import re
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk


def find_repo_root(start: Path) -> Path:
    for parent in [start, *start.parents]:
        if (parent / "data" / "_list.json").exists():
            return parent
    raise FileNotFoundError("Could not find data/_list.json from the script location.")


ROOT = find_repo_root(Path(__file__).resolve().parent)
DATA_DIR = ROOT / "data"
LIST_FILE = DATA_DIR / "_list.json"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, payload) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=4, ensure_ascii=False)
        handle.write("\n")


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]', "_", name).strip().rstrip(".")
    return cleaned or "New Level"


def level_path(level_name: str) -> Path:
    return DATA_DIR / f"{sanitize_filename(level_name)}.json"


def next_level_id() -> int:
    highest = 0
    for file_path in DATA_DIR.glob("*.json"):
        if file_path.name.startswith("_"):
            continue
        try:
            payload = load_json(file_path)
        except Exception:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("id"), int):
            highest = max(highest, payload["id"])
    return highest + 1


@dataclass
class LevelOption:
    name: str
    var: tk.BooleanVar


class ScrollableFrame(ttk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.inner = ttk.Frame(canvas)

        self.inner.bind(
            "<Configure>",
            lambda _: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        window = canvas.create_window((0, 0), window=self.inner, anchor="nw")

        def resize_inner(event):
            canvas.itemconfigure(window, width=event.width)

        canvas.bind("<Configure>", resize_inner)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.canvas = canvas


class ListEditorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("HugsButBetterList Editor")
        self.geometry("1100x760")
        self.minsize(980, 680)

        self.level_names = load_json(LIST_FILE)

        self._build_style()
        self._build_layout()
        self.refresh_all()

    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        self.configure(background="#121417")
        style.configure("TFrame", background="#121417")
        style.configure("TLabel", background="#121417", foreground="#e8e8e8")
        style.configure("Title.TLabel", font=("Segoe UI", 17, "bold"), foreground="#ffffff")
        style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"), foreground="#ffffff")
        style.configure("TButton", padding=(10, 7))
        style.configure("TEntry", padding=6)
        style.configure("TNotebook", background="#121417", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(14, 7))

    def _build_layout(self):
        header = ttk.Frame(self, padding=18)
        header.pack(fill="x")
        ttk.Label(header, text="HugsButBetterList Editor", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Add records to one or more levels, or insert a new level into the ordered list.",
        ).pack(anchor="w", pady=(4, 0))

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        self.record_tab = ttk.Frame(notebook, padding=16)
        self.game_tab = ttk.Frame(notebook, padding=16)
        notebook.add(self.record_tab, text="Add Record")
        notebook.add(self.game_tab, text="Add Game")

        self._build_record_tab()
        self._build_game_tab()

    def _build_record_tab(self):
        form = ttk.Frame(self.record_tab)
        form.pack(fill="x")

        ttk.Label(form, text="Player Name", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.record_player = tk.StringVar()
        ttk.Entry(form, textvariable=self.record_player).grid(row=1, column=0, sticky="ew", padx=(0, 12), pady=(4, 12))

        ttk.Label(form, text="Video Link", style="Section.TLabel").grid(row=0, column=1, sticky="w")
        self.record_link = tk.StringVar()
        ttk.Entry(form, textvariable=self.record_link).grid(row=1, column=1, sticky="ew", pady=(4, 12))

        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)

        meta = ttk.Frame(self.record_tab)
        meta.pack(fill="x", pady=(0, 10))
        ttk.Label(meta, text="Percent is locked to 100 for new records.").pack(anchor="w")

        controls = ttk.Frame(self.record_tab)
        controls.pack(fill="x", pady=(0, 10))
        ttk.Button(controls, text="Select All", command=self.select_all_records).pack(side="left")
        ttk.Button(controls, text="Clear All", command=self.clear_all_records).pack(side="left", padx=8)
        ttk.Button(controls, text="Scan Duplicates", command=self.scan_record_duplicates).pack(side="left", padx=8)
        ttk.Button(controls, text="Remove Duplicates", command=self.remove_record_duplicates).pack(side="left", padx=8)
        ttk.Button(controls, text="Refresh List", command=self.refresh_all).pack(side="right")

        ttk.Label(self.record_tab, text="Check every level that should receive the new record.", style="Section.TLabel").pack(anchor="w", pady=(4, 8))

        self.record_scroll = ScrollableFrame(self.record_tab)
        self.record_scroll.pack(fill="both", expand=True)
        self.record_options: list[LevelOption] = []

        self.record_submit = ttk.Button(self.record_tab, text="Add Record", command=self.add_record)
        self.record_submit.pack(anchor="e", pady=(12, 0))

    def _build_game_tab(self):
        form = ttk.Frame(self.game_tab)
        form.pack(fill="x")

        left = ttk.Frame(form)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        right = ttk.Frame(form)
        right.grid(row=0, column=1, sticky="nsew")
        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)

        self.game_name = tk.StringVar()
        self.game_author = tk.StringVar()
        self.game_verifier = tk.StringVar()
        self.game_verification = tk.StringVar()

        ttk.Label(left, text="Level Name", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Entry(left, textvariable=self.game_name).grid(row=1, column=0, sticky="ew", pady=(4, 12))
        ttk.Label(left, text="Author", style="Section.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Entry(left, textvariable=self.game_author).grid(row=3, column=0, sticky="ew", pady=(4, 12))
        left.columnconfigure(0, weight=1)

        ttk.Label(right, text="Verifier", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Entry(right, textvariable=self.game_verifier).grid(row=1, column=0, sticky="ew", pady=(4, 12))
        ttk.Label(right, text="Verification Video", style="Section.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Entry(right, textvariable=self.game_verification).grid(row=3, column=0, sticky="ew", pady=(4, 12))
        right.columnconfigure(0, weight=1)

        ttk.Label(self.game_tab, text="Description", style="Section.TLabel").pack(anchor="w")
        self.game_description = tk.Text(self.game_tab, height=5, wrap="word")
        self.game_description.pack(fill="x", pady=(4, 12))

        ttk.Label(self.game_tab, text="Creators (comma separated, optional)", style="Section.TLabel").pack(anchor="w")
        self.game_creators = tk.StringVar()
        ttk.Entry(self.game_tab, textvariable=self.game_creators).pack(fill="x", pady=(4, 12))

        ttk.Label(self.game_tab, text="Insert the new level before this mode. Choose Bottom of the List to append it.", style="Section.TLabel").pack(anchor="w", pady=(4, 8))

        game_actions = ttk.Frame(self.game_tab)
        game_actions.pack(fill="x", pady=(0, 10))
        ttk.Button(game_actions, text="Submit New Game", command=self.add_game).pack(side="right")
        ttk.Label(game_actions, text="Use this button after filling out the form and choosing a placement.").pack(side="left", anchor="w")

        placement_frame = ttk.Frame(self.game_tab)
        placement_frame.pack(fill="both", expand=True)
        self.placement_list = tk.Listbox(placement_frame, height=14, activestyle="none", exportselection=False)
        placement_scroll = ttk.Scrollbar(placement_frame, orient="vertical", command=self.placement_list.yview)
        self.placement_list.configure(yscrollcommand=placement_scroll.set)
        self.placement_list.grid(row=0, column=0, sticky="nsew")
        placement_scroll.grid(row=0, column=1, sticky="ns")
        placement_frame.columnconfigure(0, weight=1)
        placement_frame.rowconfigure(0, weight=1)

    def refresh_all(self):
        self.level_names = load_json(LIST_FILE)
        self._refresh_record_checks()
        self._refresh_placement_list()

    def _refresh_record_checks(self):
        for child in self.record_scroll.inner.winfo_children():
            child.destroy()

        self.record_options.clear()
        for row, level_name in enumerate(self.level_names):
            var = tk.BooleanVar(value=False)
            check = ttk.Checkbutton(self.record_scroll.inner, text=level_name, variable=var)
            check.grid(row=row, column=0, sticky="w", pady=2)
            self.record_options.append(LevelOption(level_name, var))

        self.record_scroll.inner.columnconfigure(0, weight=1)

    def _refresh_placement_list(self):
        self.placement_list.delete(0, tk.END)
        for level_name in self.level_names:
            self.placement_list.insert(tk.END, level_name)
        self.placement_list.insert(tk.END, "Bottom of the List")
        if self.placement_list.size() > 0:
            self.placement_list.selection_set(0)

    def select_all_records(self):
        for option in self.record_options:
            option.var.set(True)

    def clear_all_records(self):
        for option in self.record_options:
            option.var.set(False)

    def _selected_level_names(self) -> list[str]:
        return [option.name for option in self.record_options if option.var.get()]

    def _show_report(self, title: str, lines: list[str]) -> None:
        window = tk.Toplevel(self)
        window.title(title)
        window.geometry("860x560")
        window.minsize(700, 420)

        frame = ttk.Frame(window, padding=12)
        frame.pack(fill="both", expand=True)

        text = tk.Text(frame, wrap="word")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)

        text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        text.insert("1.0", "\n".join(lines) if lines else "No duplicate records were found.")
        text.configure(state="disabled")

    def scan_record_duplicates(self):
        selected_levels = self._selected_level_names() or list(self.level_names)
        if not selected_levels:
            messagebox.showinfo("No levels", "There are no levels to scan.")
            return

        report: list[str] = []
        found_any = False

        for level_name in selected_levels:
            path = level_path(level_name)
            if not path.exists():
                report.append(f"{level_name}: missing file ({path.name})")
                continue

            payload = load_json(path)
            records = payload.get("records", [])
            by_user: dict[str, list[int]] = {}
            by_link: dict[str, list[int]] = {}
            by_exact: dict[tuple[str, str], list[int]] = {}

            for index, record in enumerate(records, start=1):
                user = str(record.get("user", "")).strip()
                link = str(record.get("link", "")).strip()
                user_key = user.casefold()
                link_key = link.casefold()
                exact_key = (user_key, link_key)

                by_user.setdefault(user_key, []).append(index)
                by_link.setdefault(link_key, []).append(index)
                by_exact.setdefault(exact_key, []).append(index)

            level_lines: list[str] = []

            exact_duplicates = [indexes for indexes in by_exact.values() if len(indexes) > 1 and indexes[0] is not None]
            for indexes in exact_duplicates:
                found_any = True
                level_lines.append(f"Exact duplicate records at positions {', '.join(map(str, indexes))}")

            for user_key, indexes in by_user.items():
                if user_key and len(indexes) > 1:
                    found_any = True
                    level_lines.append(f"Same user name at positions {', '.join(map(str, indexes))}")

            for link_key, indexes in by_link.items():
                if link_key and len(indexes) > 1:
                    found_any = True
                    level_lines.append(f"Same video link at positions {', '.join(map(str, indexes))}")

            if level_lines:
                report.append(f"{level_name}:")
                report.extend(f"  - {line}" for line in level_lines)

        if not found_any:
            report = ["No duplicate records were found in the selected levels."]

        self._show_report("Duplicate Record Scan", report)

    def remove_record_duplicates(self):
        selected_levels = self._selected_level_names() or list(self.level_names)
        if not selected_levels:
            messagebox.showinfo("No levels", "There are no levels to clean.")
            return

        changed_levels: list[str] = []
        skipped_levels: list[str] = []

        for level_name in selected_levels:
            path = level_path(level_name)
            if not path.exists():
                skipped_levels.append(f"{level_name} (missing file)")
                continue

            payload = load_json(path)
            records = payload.get("records", [])
            if not isinstance(records, list) or not records:
                continue

            best_by_record: dict[tuple[str, str], tuple[int, dict]] = {}
            order: list[tuple[str, str]] = []

            for index, record in enumerate(records):
                if not isinstance(record, dict):
                    continue

                user = str(record.get("user", "")).strip()
                link = str(record.get("link", "")).strip()
                percent = record.get("percent", 0)
                try:
                    percent_value = float(percent)
                except (TypeError, ValueError):
                    percent_value = 0.0

                key = (user.casefold(), link.casefold())
                existing = best_by_record.get(key)
                if existing is None:
                    best_by_record[key] = (index, record)
                    order.append(key)
                    continue

                existing_index, existing_record = existing
                existing_percent = existing_record.get("percent", 0)
                try:
                    existing_percent_value = float(existing_percent)
                except (TypeError, ValueError):
                    existing_percent_value = 0.0

                if percent_value > existing_percent_value:
                    best_by_record[key] = (index, record)
                elif percent_value == existing_percent_value and index < existing_index:
                    best_by_record[key] = (index, record)

            deduped_records = [best_by_record[key][1] for key in order]
            if len(deduped_records) != len(records):
                payload["records"] = deduped_records
                save_json(path, payload)
                changed_levels.append(f"{level_name}: {len(records)} -> {len(deduped_records)}")

        if changed_levels:
            self.refresh_all()
            self._show_report(
                "Duplicate Cleanup",
                ["Cleaned exact duplicate records while keeping the highest percent entry."] + changed_levels,
            )
            return

        if skipped_levels:
            self._show_report("Duplicate Cleanup", ["No duplicate records were changed."] + skipped_levels)
            return

        messagebox.showinfo("Duplicate Cleanup", "No duplicate records were changed.")

    def add_record(self):
        player = self.record_player.get().strip()
        link = self.record_link.get().strip()
        selected_levels = self._selected_level_names()

        if not player or not link:
            messagebox.showerror("Missing info", "Enter both the player name and the video link.")
            return
        if not selected_levels:
            messagebox.showerror("No levels selected", "Select at least one level to receive the record.")
            return

        updated_files = []
        for level_name in selected_levels:
            path = level_path(level_name)
            if not path.exists():
                messagebox.showerror("Missing level file", f"Could not find {path.name}.")
                return

            payload = load_json(path)
            records = payload.setdefault("records", [])
            records.append({"user": player, "link": link, "percent": 100})
            save_json(path, payload)
            updated_files.append(path.name)

        messagebox.showinfo(
            "Record added",
            f"Added the record to {len(updated_files)} level(s):\n" + "\n".join(updated_files),
        )

    def add_game(self):
        name = self.game_name.get().strip()
        author = self.game_author.get().strip()
        verifier = self.game_verifier.get().strip()
        verification = self.game_verification.get().strip()
        description = self.game_description.get("1.0", tk.END).strip()
        creators_text = self.game_creators.get().strip()

        if not all([name, author, verifier, verification, description]):
            messagebox.showerror(
                "Missing info",
                "Fill out the level name, author, verifier, verification video, and description.",
            )
            return

        selection = self.placement_list.curselection()
        if not selection:
            messagebox.showerror("No placement selected", "Choose a mode to insert before, or Bottom of the List.")
            return

        insert_index = selection[0]
        if insert_index >= len(self.level_names):
            insert_index = len(self.level_names)

        new_file = level_path(name)
        if new_file.exists():
            messagebox.showerror("Level already exists", f"{new_file.name} already exists.")
            return

        level_id = next_level_id()
        creators = [part.strip() for part in creators_text.split(",") if part.strip()]
        if not creators:
            creators = [author]

        payload = {
            "id": level_id,
            "name": name,
            "author": author,
            "creators": creators,
            "verifier": verifier,
            "verification": verification,
            "description": description,
            "percentToQualify": 100,
            "records": [],
        }

        save_json(new_file, payload)
        self.level_names.insert(insert_index, name)
        save_json(LIST_FILE, self.level_names)
        self.refresh_all()

        messagebox.showinfo(
            "Game added",
            f"Added {name} at position {insert_index + 1}.\nCreated {new_file.name}.",
        )


def main() -> None:
    app = ListEditorApp()
    app.mainloop()


if __name__ == "__main__":
    main()