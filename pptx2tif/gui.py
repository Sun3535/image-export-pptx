"""Popup window: pick .pptx files and save their images as TIFF next to them."""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .extractor import extract_images
from .models import STATUS_ERROR, STATUS_OK
from .tiff import COMPRESSIONS

MIN_PPI = 150.0


def _clean_path(text: str) -> str:
    # "Copy as path" in Windows Explorer wraps the path in quotes.
    return text.strip().strip('"').strip("'").strip()


def _open_folder(path: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.files: list[Path] = []
        self.events: queue.Queue = queue.Queue()
        self.last_target: Path | None = None

        root.title("PPTX 이미지 → TIFF 추출")
        root.minsize(720, 520)
        frm = ttk.Frame(root, padding=12)
        frm.grid(sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        frm.columnconfigure(0, weight=1)

        ttk.Label(frm, text="PPTX 파일 또는 폴더 경로 (직접 입력 후 Enter, 또는 [찾아보기])").grid(
            row=0, column=0, columnspan=3, sticky="w")
        self.path_var = tk.StringVar()
        entry = ttk.Entry(frm, textvariable=self.path_var)
        entry.grid(row=1, column=0, sticky="ew", pady=4)
        entry.bind("<Return>", lambda _e: self.add_typed())
        entry.focus_set()
        ttk.Button(frm, text="추가", command=self.add_typed).grid(row=1, column=1, padx=4)
        ttk.Button(frm, text="찾아보기...", command=self.browse).grid(row=1, column=2)

        ttk.Label(frm, text="추출할 파일").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.listbox = tk.Listbox(frm, height=6, selectmode="extended")
        self.listbox.grid(row=3, column=0, sticky="nsew")
        side = ttk.Frame(frm)
        side.grid(row=3, column=1, columnspan=2, sticky="n", padx=4)
        ttk.Button(side, text="선택 삭제", command=self.remove_selected).pack(fill="x")
        ttk.Button(side, text="모두 지우기", command=self.clear).pack(fill="x", pady=4)

        ttk.Label(
            frm,
            text='저장 위치: 각 PPTX와 같은 폴더 안에 "PPTX 이름" 폴더가 만들어지고 그 안에 TIFF가 저장돼요.',
            foreground="#2f5d8a",
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 4))

        opts = ttk.Frame(frm)
        opts.grid(row=5, column=0, columnspan=3, sticky="w")
        ttk.Label(opts, text="압축(모두 무손실):").pack(side="left")
        self.compression = tk.StringVar(value="deflate")
        ttk.Combobox(opts, textvariable=self.compression, values=COMPRESSIONS,
                     state="readonly", width=9).pack(side="left", padx=(4, 16))
        self.keep_original = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="원본 이미지 파일도 함께 저장",
                        variable=self.keep_original).pack(side="left")

        self.run_btn = ttk.Button(frm, text="추출 시작", command=self.start)
        self.run_btn.grid(row=6, column=0, columnspan=3, sticky="ew", pady=8)

        self.log = tk.Text(frm, height=12, state="disabled", wrap="word")
        self.log.grid(row=7, column=0, columnspan=2, sticky="nsew")
        scroll = ttk.Scrollbar(frm, command=self.log.yview)
        scroll.grid(row=7, column=2, sticky="nsw")
        self.log["yscrollcommand"] = scroll.set
        frm.rowconfigure(3, weight=1)
        frm.rowconfigure(7, weight=2)

        self.open_btn = ttk.Button(frm, text="결과 폴더 열기", state="disabled",
                                   command=lambda: self.last_target and _open_folder(self.last_target))
        self.open_btn.grid(row=8, column=0, columnspan=3, sticky="e", pady=(8, 0))

    # --- file list -------------------------------------------------------
    def _add(self, path: Path) -> bool:
        path = path.expanduser()
        if path.is_dir():
            found = sorted(p for p in path.glob("*.pptx") if not p.name.startswith("~$"))
            if not found:
                messagebox.showwarning("파일 없음", f"이 폴더에 .pptx 파일이 없어요:\n{path}")
                return False
            for p in found:
                self._add(p)
            return True
        if not path.is_file():
            messagebox.showerror("경로 오류", f"파일을 찾을 수 없어요:\n{path}")
            return False
        if path.suffix.lower() != ".pptx":
            messagebox.showerror("형식 오류", f".pptx 파일만 지원해요:\n{path}")
            return False
        path = path.resolve()
        if path not in self.files:
            self.files.append(path)
            self.listbox.insert("end", str(path))
        return True

    def add_typed(self) -> None:
        text = _clean_path(self.path_var.get())
        if text and self._add(Path(text)):
            self.path_var.set("")

    def browse(self) -> None:
        paths = filedialog.askopenfilenames(
            title="PPTX 파일 선택",
            filetypes=[("PowerPoint 파일", "*.pptx"), ("모든 파일", "*.*")],
        )
        for p in paths:
            self._add(Path(p))

    def remove_selected(self) -> None:
        for i in reversed(self.listbox.curselection()):
            self.listbox.delete(i)
            del self.files[i]

    def clear(self) -> None:
        self.listbox.delete(0, "end")
        self.files.clear()

    # --- extraction ------------------------------------------------------
    def _write(self, line: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def start(self) -> None:
        text = _clean_path(self.path_var.get())
        if text:  # a path typed but not yet added: add it, stop if it is invalid
            if not self._add(Path(text)):
                return
            self.path_var.set("")
        if not self.files:
            messagebox.showinfo("파일 선택", "먼저 PPTX 파일을 추가해 주세요.")
            return
        self.run_btn.configure(state="disabled")
        self.open_btn.configure(state="disabled")
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        args = (list(self.files), self.compression.get(), self.keep_original.get())
        threading.Thread(target=self._work, args=args, daemon=True).start()
        self.root.after(100, self._poll)

    def _work(self, files: list[Path], compression: str, keep_original: bool) -> None:
        saved = warns = errors = 0
        for f in files:
            self.events.put(("log", f"▶ {f.name} 처리 중..."))
            try:
                records = extract_images(f, None, compression, keep_original, MIN_PPI)
            except Exception as exc:
                self.events.put(("log", f"  [오류] {exc}"))
                errors += 1
                continue
            target = f.parent / f.stem
            n = sum(1 for r in records if r.status == STATUS_OK and r.output_path)
            self.events.put(("log", f"  TIFF {n}장 저장 → {target}"))
            for r in records:
                if r.message:
                    tag = "오류" if r.status == STATUS_ERROR else "경고"
                    self.events.put(("log", f"  [{tag}] 슬라이드 {r.slide_index} 이미지 "
                                            f"{r.image_index}: {r.message}"))
            saved += n
            errors += sum(1 for r in records if r.status == STATUS_ERROR)
            warns += sum(1 for r in records if r.message and r.status != STATUS_ERROR)
            self.events.put(("target", target))
        self.events.put(("done", (saved, warns, errors)))

    def _poll(self) -> None:
        while True:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self._write(value)
            elif kind == "target":
                self.last_target = value
                self.open_btn.configure(state="normal")
            elif kind == "done":
                saved, warns, errors = value
                summary = f"완료: TIFF {saved}장 저장, 경고 {warns}건, 오류 {errors}건"
                self._write("\n" + summary)
                self.run_btn.configure(state="normal")
                (messagebox.showwarning if errors else messagebox.showinfo)("완료", summary)
                return
        self.root.after(100, self._poll)


def main() -> None:
    if sys.platform.startswith("win"):
        try:  # sharp text on high-DPI Windows displays
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
