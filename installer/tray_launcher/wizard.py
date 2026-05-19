"""First-run wizard - small Tk window walking the user through setup.

3 steps:
  1. Welcome
  2. Docker check + initial data sync confirmation (~1h background task)
  3. Done

Returns True on completion, False if user cancels.
"""
from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

logger = logging.getLogger("z1n_launcher.wizard")


class Wizard:
    BRAND_TEAL = "#0F766E"
    BG = "#F8FAFC"

    def __init__(self):
        self.completed = False
        self.root = tk.Tk()
        self.root.title("Z1N MF Analyser - Setup")
        self.root.geometry("520x360")
        self.root.configure(bg=self.BG)
        self.root.resizable(False, False)
        self.step = 0
        self.frame = None
        self._build()

    def _build(self):
        self._show_step()

    def _clear(self):
        if self.frame is not None:
            self.frame.destroy()
        self.frame = tk.Frame(self.root, bg=self.BG, padx=24, pady=20)
        self.frame.pack(fill="both", expand=True)

    def _heading(self, text: str):
        tk.Label(
            self.frame, text=text, font=("Segoe UI", 16, "bold"),
            fg=self.BRAND_TEAL, bg=self.BG,
        ).pack(anchor="w", pady=(0, 8))

    def _body(self, text: str):
        tk.Label(
            self.frame, text=text, font=("Segoe UI", 10), fg="#0F172A", bg=self.BG,
            justify="left", wraplength=470,
        ).pack(anchor="w", pady=(0, 16))

    def _nav(self, next_text="Next", prev=True):
        bar = tk.Frame(self.frame, bg=self.BG)
        bar.pack(side="bottom", fill="x", pady=(20, 0))
        tk.Button(bar, text="Cancel", command=self._cancel).pack(side="left")
        if prev and self.step > 0:
            tk.Button(bar, text="Back", command=self._back).pack(side="right", padx=(0, 6))
        tk.Button(
            bar, text=next_text, command=self._next,
            bg=self.BRAND_TEAL, fg="white", relief="flat", padx=12, pady=4,
        ).pack(side="right", padx=(6, 6))

    def _show_step(self):
        self._clear()
        if self.step == 0:
            self._heading("Welcome to Z1N MF Analyser")
            self._body(
                "This brief setup will start the analytics service and run an "
                "initial data sync of Indian mutual funds and ETFs.\n\n"
                "Please ensure Docker Desktop is installed and running before "
                "continuing."
            )
            self._nav("Continue", prev=False)
        elif self.step == 1:
            self._heading("Initial data sync")
            self._body(
                "On first launch the app will download the full mutual-fund "
                "universe and ~3 years of NAV history. This takes roughly "
                "60-90 minutes and runs in the background.\n\n"
                "You can use the dashboard right away; new data will appear "
                "as the sync progresses."
            )
            self._nav("Start sync", prev=True)
        elif self.step == 2:
            self._heading("All set")
            self._body(
                "The dashboard will open in your browser. The Z1N icon now "
                "lives in the system tray (bottom-right corner).\n\n"
                "Right-click it any time to open the dashboard, view logs, "
                "or quit the app."
            )
            self._nav("Finish", prev=False)

    def _next(self):
        if self.step >= 2:
            self.completed = True
            self.root.destroy()
            return
        self.step += 1
        self._show_step()

    def _back(self):
        if self.step > 0:
            self.step -= 1
            self._show_step()

    def _cancel(self):
        self.completed = False
        self.root.destroy()

    def run(self) -> bool:
        self.root.mainloop()
        return self.completed


def run_wizard() -> bool:
    return Wizard().run()


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    logging.basicConfig(level=logging.INFO)
    print("completed:", run_wizard())
