"""교대 인수인계 보고서 — 데스크톱 앱 (tkinter).

실행: python app.py
"""
import os
import queue
import re
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from handover.batch import find_memos, run_batch
from handover.config import load_api_key
from handover.files import read_memo_file
from handover.insights import extract_insights, load_insights, save_insights
from handover.llm import MODEL, ReportError
from handover.schema import HandoverReport
from handover.service import generate
from handover.store import Record, load_records, sort_for_dashboard
from handover.view import EMPTY, build_sections, unconfirmed_ranking

BASE_DIR = Path(__file__).resolve().parent

# ---- 디자인 토큰 -------------------------------------------------------------
BG = "#F3F5F9"
SURFACE = "#FFFFFF"
SUBTLE = "#F8FAFC"
BORDER = "#E2E8F0"
TEXT = "#0F172A"
MUTED = "#64748B"
FAINT = "#94A3B8"
PRIMARY = "#2563EB"
PRIMARY_HOVER = "#1D4ED8"
PRIMARY_SOFT = "#EFF6FF"
HEADER = "#0F172A"
HEADER_MUTED = "#94A3B8"
HEADER_RAISED = "#1E293B"

BANNERS = {  # 종류: (배경, 테두리, 글자, 아이콘)
    "success": ("#ECFDF5", "#A7F3D0", "#047857", "✓"),
    "warning": ("#FFFBEB", "#FCD34D", "#B45309", "!"),
    "error": ("#FEF2F2", "#FECACA", "#B91C1C", "✕"),
    "info": ("#EFF6FF", "#BFDBFE", "#1D4ED8", "i"),
}
ACCENTS = {
    "events": "#2563EB",
    "actions": "#059669",
    "status": "#7C3AED",
    "checks": "#EA580C",
    "timeline": "#0891B2",
    "facts": "#475569",
    "contacts": "#DB2777",
    "unconfirmed": "#D97706",
}
UNCONFIRMED_BG = "#FFFBEB"
PRIORITY_COLORS = {  # 긴급도: (강조색, 옅은 배경)
    "긴급": ("#DC2626", "#FEF2F2"),
    "주의": ("#D97706", "#FFFBEB"),
    "일반": ("#059669", "#F0FDF4"),
}

_REPORT_NAME = re.compile(r"^인수인계_(?P<stem>.+)_(?P<d>\d{8})_(?P<t>\d{6})(?:_\d+)?$")


class Fonts:
    def __init__(self, root: tk.Misc):
        families = set(tkfont.families(root))
        base = next((f for f in ("Malgun Gothic", "맑은 고딕", "Apple SD Gothic Neo", "Noto Sans KR")
                     if f in families), "TkDefaultFont")
        mono = next((f for f in ("D2Coding", "Consolas", "Menlo") if f in families), "TkFixedFont")
        self.brand = (base, 15, "bold")
        self.title = (base, 12, "bold")
        self.hero = (base, 13, "bold")
        self.stat = (base, 22, "bold")
        self.body = (base, 10)
        self.body_bold = (base, 10, "bold")
        self.editor = (base, 11)
        self.small = (base, 9)
        self.small_bold = (base, 9, "bold")
        self.icon = (base, 30)
        self.mono = (mono, 10)


class Button(tk.Label):
    """평평한 버튼 (hover·비활성 상태 포함). ttk 버튼보다 현대적인 모양을 위해 Label로 만든다."""

    STYLES = {
        "primary": (PRIMARY, "#FFFFFF", PRIMARY_HOVER, PRIMARY),
        "secondary": (SURFACE, TEXT, SUBTLE, BORDER),
        "ghost": (SURFACE, MUTED, SUBTLE, SURFACE),
    }

    def __init__(self, master, text, command, kind="secondary", font=None, **kw):
        bg, fg, hover, border = self.STYLES[kind]
        super().__init__(master, text=text, bg=bg, fg=fg, font=font, cursor="hand2",
                         padx=14, pady=7, highlightthickness=1, highlightbackground=border, **kw)
        self._colors = (bg, fg, hover)
        self._command = command
        self._enabled = True
        self.bind("<Enter>", lambda e: self._enabled and self.configure(bg=hover))
        self.bind("<Leave>", lambda e: self.configure(bg=bg))
        self.bind("<Button-1>", lambda e: self._enabled and self._command())

    def set_enabled(self, enabled: bool):
        bg, fg, _ = self._colors
        self._enabled = enabled
        self.configure(fg=fg if enabled else FAINT, bg=bg, cursor="hand2" if enabled else "arrow")


class Card(tk.Frame):
    def __init__(self, master, **kw):
        super().__init__(master, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER, **kw)


def card_header(card, fonts: Fonts, title: str, subtitle: str):
    head = tk.Frame(card, bg=SURFACE)
    head.pack(fill="x", padx=20, pady=(18, 12))
    # 버튼 영역을 먼저 배치해야 창이 좁아져도 버튼이 잘리지 않는다 (pack은 먼저 넣은 것에 공간을 먼저 준다)
    actions = tk.Frame(head, bg=SURFACE)
    actions.pack(side="right", anchor="n")
    text = tk.Frame(head, bg=SURFACE)
    text.pack(side="left", fill="x", expand=True)
    tk.Label(text, text=title, bg=SURFACE, fg=TEXT, font=fonts.title).pack(anchor="w")
    sub = tk.Label(text, text=subtitle, bg=SURFACE, fg=MUTED, font=fonts.small, anchor="w", justify="left")
    sub.pack(anchor="w", pady=(2, 0))
    return sub, actions


class ScrollArea(tk.Frame):
    """세로 스크롤 영역. 마우스 휠은 커서가 영역 안에 있을 때만 동작."""

    def __init__(self, master, bg=SURFACE):
        super().__init__(master, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview,
                                       style="Slim.Vertical.TScrollbar")
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner.bind("<Configure>", self._update_scroll)
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._on_wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _on_canvas_resize(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)
        self._update_scroll()

    def _update_scroll(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        overflow = self.inner.winfo_reqheight() > self.canvas.winfo_height()
        if overflow and not self.scrollbar.winfo_ismapped():
            self.scrollbar.pack(side="right", fill="y")
        elif not overflow and self.scrollbar.winfo_ismapped():
            self.scrollbar.pack_forget()

    def _on_wheel(self, event):
        if not self.scrollbar.winfo_ismapped():
            return
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def clear(self):
        for child in self.inner.winfo_children():
            child.destroy()
        self.canvas.yview_moveto(0)


class ReportView(Card):
    """보고서 한 건을 보여주는 카드: 배너 + 긴급도·요약 + 항목별 카드. 두 탭에서 함께 쓴다."""

    def __init__(self, master, root: tk.Misc, fonts: Fonts, title: str, empty_title: str, empty_hint: str):
        super().__init__(master)
        self.root = root
        self.fonts = fonts
        self._text = ""
        self._path: Path | None = None
        self._banner_text = ""
        self._hero_text = ""
        self._wrap_labels: list[tk.Label] = []
        f = fonts

        self.meta_label, actions = card_header(self, f, title, "생성된 보고서가 여기에 표시됩니다")
        self.open_button = Button(actions, "파일 열기", self._open, font=f.body)
        self.open_button.pack(side="right", padx=(8, 0))
        self.copy_button = Button(actions, "복사", self._copy, font=f.body)
        self.copy_button.pack(side="right")
        self.copy_button.set_enabled(False)
        self.open_button.set_enabled(False)

        self.banner_anchor = tk.Frame(self, bg=SURFACE, height=0)
        self.banner_anchor.pack(fill="x", padx=20)
        self.banner = tk.Frame(self, highlightthickness=1)
        self.banner_icon = tk.Label(self.banner, font=f.body_bold, width=2)
        self.banner_icon.pack(side="left", anchor="n", padx=(12, 4), pady=10)
        self.banner_body = tk.Frame(self.banner)
        self.banner_body.pack(side="left", fill="x", expand=True, pady=10, padx=(0, 12))

        self.content = tk.Frame(self, bg=SURFACE)
        self.content.pack(fill="both", expand=True, padx=20, pady=(8, 20))

        self.empty_state = tk.Frame(self.content, bg=SURFACE)
        inner = tk.Frame(self.empty_state, bg=SURFACE)
        inner.place(relx=0.5, rely=0.45, anchor="center")
        tk.Label(inner, text="📋", bg=SURFACE, fg=FAINT, font=f.icon).pack()
        tk.Label(inner, text=empty_title, bg=SURFACE, fg=TEXT, font=f.title).pack(pady=(10, 4))
        tk.Label(inner, text=empty_hint, bg=SURFACE, fg=MUTED, font=f.small).pack()

        self.loading_state = tk.Frame(self.content, bg=SURFACE)
        inner = tk.Frame(self.loading_state, bg=SURFACE)
        inner.place(relx=0.5, rely=0.45, anchor="center")
        tk.Label(inner, text="Claude가 메모를 정리하고 있습니다…", bg=SURFACE, fg=TEXT, font=f.title).pack()
        tk.Label(inner, text="보통 10~30초 걸립니다. 메모에 없는 내용은 ‘미확인’으로 표시됩니다.",
                 bg=SURFACE, fg=MUTED, font=f.small).pack(pady=(4, 14))
        self.progress = ttk.Progressbar(inner, mode="indeterminate", length=320,
                                        style="Accent.Horizontal.TProgressbar")
        self.progress.pack()

        self.result_area = ScrollArea(self.content)
        self.result_area.inner.bind("<Configure>", self._rewrap, add="+")
        self.text_view = tk.Text(self.content, wrap="word", font=f.mono, bg=SUBTLE, fg=TEXT, relief="flat",
                                 padx=16, pady=14, highlightthickness=1, highlightbackground=BORDER)
        self.show_state("empty")

    # ---- 상태 ------------------------------------------------------------------
    def show_state(self, name: str):
        for state in (self.empty_state, self.loading_state, self.result_area, self.text_view):
            state.pack_forget()
        target = {"empty": self.empty_state, "loading": self.loading_state,
                  "result": self.result_area, "text": self.text_view}[name]
        target.pack(fill="both", expand=True)
        if name == "loading":
            self.progress.start(12)
        else:
            self.progress.stop()

    def set_banner(self, kind: str | None, title: str = "", lines: list[str] | None = None):
        self._banner_text = "\n".join([title, *(lines or [])]).strip()
        for child in self.banner_body.winfo_children():
            child.destroy()
        if kind is None:
            self.banner.pack_forget()
            return
        bg, border, fg, icon = BANNERS[kind]
        self.banner.configure(bg=bg, highlightbackground=border)
        self.banner_body.configure(bg=bg)
        self.banner_icon.configure(text=icon, bg=bg, fg=fg)
        tk.Label(self.banner_body, text=title, bg=bg, fg=fg, font=self.fonts.body_bold, anchor="w",
                 justify="left", wraplength=420).pack(fill="x")
        for line in lines or []:
            tk.Label(self.banner_body, text=f"• {line}", bg=bg, fg=fg, font=self.fonts.small,
                     anchor="w", justify="left", wraplength=420).pack(fill="x", pady=(2, 0))
        self.banner.pack(in_=self.banner_anchor, fill="x", pady=(0, 4))
        self.banner.lift(self.banner_anchor)  # anchor보다 나중에 그려야 가려지지 않는다

    def status_text(self) -> str:
        return "\n".join(filter(None, [self._hero_text, self._banner_text]))

    # ---- 표시 ------------------------------------------------------------------
    def show_report(self, report: HandoverReport, warnings: list[str], source_name: str, path: Path, text: str):
        self._text, self._path = text, path
        self.copy_button.set_enabled(bool(text))
        self.open_button.set_enabled(True)
        self.meta_label.configure(text=f"{source_name}  ·  {path.name}")
        if warnings:
            self.set_banner("warning", f"자동 점검 경고 {len(warnings)}건 — 원문과 대조해 확인하세요", warnings)
        else:
            self.set_banner("success", "자동 점검: 이상 없음 — 원문에 없는 숫자·단정 표현이 발견되지 않았습니다")
        self._render(report)
        self.show_state("result")

    def show_record(self, record: Record):
        try:
            text = record.txt_path.read_text(encoding="utf-8")
        except OSError:
            text = ""
        self.show_report(record.report, record.warnings, record.source_name, record.txt_path, text)

    def show_text(self, text: str, path: Path):
        self._text, self._path = text, path
        self._hero_text = ""
        self.copy_button.set_enabled(True)
        self.open_button.set_enabled(True)
        self.meta_label.configure(text=f"저장된 보고서  ·  {path.name}")
        self.set_banner("info", "저장된 보고서를 보고 있습니다",
                        ["새 보고서를 만들려면 메모를 입력하고 ‘보고서 생성’을 누르세요."])
        self.text_view.configure(state="normal")
        self.text_view.delete("1.0", "end")
        self.text_view.insert("1.0", text)
        self.text_view.configure(state="disabled")
        self.show_state("text")

    def _render(self, report: HandoverReport):
        f = self.fonts
        self.result_area.clear()
        self._wrap_labels = []
        inner = self.result_area.inner

        accent, tint = PRIORITY_COLORS[report.priority]
        self._hero_text = f"[{report.priority}] {report.priority_reason}\n{report.summary}"
        hero = tk.Frame(inner, bg=tint, highlightthickness=1, highlightbackground=accent)
        hero.pack(fill="x", pady=(0, 14), padx=(0, 8))
        top = tk.Frame(hero, bg=tint)
        top.pack(fill="x", padx=16, pady=(14, 4))
        tk.Label(top, text=f" {report.priority} ", bg=accent, fg="#FFFFFF", font=f.body_bold,
                 padx=6, pady=2).pack(side="left")
        tk.Label(top, text="긴급도", bg=tint, fg=MUTED, font=f.small).pack(side="left", padx=8)
        summary = tk.Label(hero, text=report.summary or "요약 없음", bg=tint, fg=TEXT, font=f.hero,
                           anchor="w", justify="left")
        summary.pack(fill="x", padx=16)
        reason = tk.Label(hero, text=f"판단 이유 · {report.priority_reason}", bg=tint, fg=MUTED, font=f.body,
                          anchor="w", justify="left")
        reason.pack(fill="x", padx=16, pady=(4, 14))
        self._wrap_labels += [summary, reason]

        for section in build_sections(report):
            accent = ACCENTS[section.kind]
            bg = UNCONFIRMED_BG if section.kind == "unconfirmed" else SURFACE
            outer = tk.Frame(inner, bg=bg, highlightthickness=1,
                             highlightbackground="#FDE68A" if section.kind == "unconfirmed" else BORDER)
            outer.pack(fill="x", pady=(0, 12), padx=(0, 8))
            tk.Frame(outer, bg=accent, width=4).pack(side="left", fill="y")
            box = tk.Frame(outer, bg=bg)
            box.pack(side="left", fill="both", expand=True, padx=16, pady=12)

            head = tk.Frame(box, bg=bg)
            head.pack(fill="x")
            tk.Label(head, text=section.title, bg=bg, fg=TEXT, font=f.title).pack(side="left")
            real = [line for line in section.lines if line != EMPTY]
            if real:
                tk.Label(head, text=f"{len(real)}건", bg=accent, fg="#FFFFFF", font=f.small_bold,
                         padx=7).pack(side="left", padx=8)

            for line in section.lines:
                row = tk.Frame(box, bg=bg)
                row.pack(fill="x", pady=(6, 0))
                if line == EMPTY:
                    label = tk.Label(row, text=line, bg=bg, fg=FAINT, font=f.body, anchor="w", justify="left")
                    label.pack(side="left", fill="x", expand=True)
                else:
                    tk.Label(row, text="●", bg=bg, fg=accent, font=f.small).pack(side="left", anchor="n", pady=2)
                    label = tk.Label(row, text=line, bg=bg, fg=TEXT, font=f.body, anchor="w", justify="left")
                    label.pack(side="left", fill="x", expand=True, padx=(8, 0))
                self._wrap_labels.append(label)
        self._rewrap()

    def _rewrap(self, _event=None):
        width = max(self.result_area.inner.winfo_width() - 90, 200)
        for label in self._wrap_labels:
            if label.winfo_exists():
                label.configure(wraplength=width)

    # ---- 동작 ------------------------------------------------------------------
    def _copy(self):
        if not self._text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self._text)
        self.copy_button.configure(text="복사됨 ✓")
        self.root.after(1500, lambda: self.copy_button.configure(text="복사"))

    def _open(self):
        if self._path and self._path.exists():
            _open_path(self._path)


class HandoverApp:
    def __init__(self, root: tk.Misc, client_factory, out_dir: Path, samples_dir: Path,
                 runner=None, api_ready: bool | None = None):
        self.root = root
        self.client_factory = client_factory
        self.out_dir = Path(out_dir)
        self.samples_dir = Path(samples_dir)
        self.batch_folder = Path(samples_dir)
        self.runner = runner or (lambda fn: threading.Thread(target=fn, daemon=True).start())
        self.api_ready = api_ready
        self.fonts = Fonts(root)
        self.history_paths: list[Path] = []
        self._records: list[Record] = []
        self._results: queue.Queue = queue.Queue()
        self._busy = False
        self._batch_busy = False
        self._batch_total = 0
        self._batch_done = 0
        self._batch_failed: list[str] = []
        self._insights_busy = False
        self._insight_snapshot = load_insights(self.out_dir)
        self._insight_message: tuple[str, str] | None = None  # (종류, 문구) — 분석 중/오류/안내
        self._client = None
        self._client_lock = threading.Lock()
        self._source_name = "직접 입력"
        self._source_stem = "입력"
        self._tabs: dict[str, tk.Label] = {}
        self._views: dict[str, tk.Frame] = {}

        self._setup_root()
        self._build_header()
        self.body = tk.Frame(self.root, bg=BG)
        self.body.pack(fill="both", expand=True, padx=20, pady=20)
        self._views["editor"] = self._build_editor_tab(self.body)
        self._views["dashboard"] = self._build_dashboard_tab(self.body)
        self.refresh_history()
        self.refresh_dashboard()
        self.show_tab("dashboard")  # 첫 화면은 대시보드

    # ---- 공통 레이아웃 ------------------------------------------------------------
    def _setup_root(self):
        self.root.title("교대 인수인계 보고서")
        self.root.configure(bg=BG)
        self.root.geometry("1360x860")
        self.root.minsize(1120, 720)
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Accent.Horizontal.TProgressbar", troughcolor="#E2E8F0", background=PRIMARY,
                        bordercolor="#E2E8F0", lightcolor=PRIMARY, darkcolor=PRIMARY, thickness=6)
        style.layout("Slim.Vertical.TScrollbar",
                     [("Vertical.Scrollbar.trough", {"sticky": "ns",
                       "children": [("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        style.configure("Slim.Vertical.TScrollbar", troughcolor=SURFACE, background="#CBD5E1",
                        bordercolor=SURFACE, lightcolor="#CBD5E1", darkcolor="#CBD5E1", width=8)
        style.map("Slim.Vertical.TScrollbar", background=[("active", "#94A3B8")])
        f = self.fonts
        style.configure("Dash.Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=TEXT,
                        bordercolor=SURFACE, rowheight=38, font=f.body)
        style.configure("Dash.Treeview.Heading", background=SUBTLE, foreground=MUTED, font=f.small_bold,
                        relief="flat", bordercolor=BORDER, padding=(8, 8))
        style.map("Dash.Treeview", background=[("selected", PRIMARY_SOFT)], foreground=[("selected", TEXT)])
        style.map("Dash.Treeview.Heading", background=[("active", SUBTLE)])
        self.root.bind("<Control-Return>", lambda e: (self.generate(), "break")[1])

    def _build_header(self):
        f = self.fonts
        header = tk.Frame(self.root, bg=HEADER, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)

        brand = tk.Frame(header, bg=HEADER)
        brand.pack(side="left", padx=24)
        tk.Label(brand, text="인", bg=PRIMARY, fg="#FFFFFF", font=f.title, width=2, pady=2).pack(side="left", pady=16)
        titles = tk.Frame(brand, bg=HEADER)
        titles.pack(side="left", padx=12)
        tk.Label(titles, text="교대 인수인계", bg=HEADER, fg="#FFFFFF", font=f.brand).pack(anchor="w")
        tk.Label(titles, text="작업 메모를 다음 근무자용 보고서로 정리합니다", bg=HEADER, fg=HEADER_MUTED,
                 font=f.small).pack(anchor="w")

        tabs = tk.Frame(header, bg=HEADER_RAISED, padx=4, pady=4)
        tabs.pack(side="left", padx=40)
        for key, label in (("dashboard", "대시보드"), ("editor", "메모 작성")):
            tab = tk.Label(tabs, text=label, font=f.body_bold, padx=18, pady=6, cursor="hand2")
            tab.pack(side="left")
            tab.bind("<Button-1>", lambda e, k=key: self.show_tab(k))
            self._tabs[key] = tab

        status = tk.Frame(header, bg=HEADER)
        status.pack(side="right", padx=24)
        if self.api_ready is None:
            dot, label = FAINT, "Claude API"
        elif self.api_ready:
            dot, label = "#34D399", "Claude API 연결 준비됨"
        else:
            dot, label = "#F87171", "API 키 없음 · .env 확인"
        pill = tk.Frame(status, bg=HEADER_RAISED, padx=12, pady=5)
        pill.pack(side="right")
        tk.Label(pill, text="●", bg=HEADER_RAISED, fg=dot, font=f.small).pack(side="left")
        tk.Label(pill, text=f" {label}", bg=HEADER_RAISED, fg="#E2E8F0", font=f.small_bold).pack(side="left")
        tk.Label(pill, text=f"  ·  {MODEL}", bg=HEADER_RAISED, fg=HEADER_MUTED, font=f.small).pack(side="left")

    def show_tab(self, name: str):
        self.current_tab = name
        for key, view in self._views.items():
            view.pack_forget()
            active = key == name
            self._tabs[key].configure(bg=SURFACE if active else HEADER_RAISED,
                                      fg=TEXT if active else HEADER_MUTED)
        self._views[name].pack(fill="both", expand=True)
        if name == "dashboard":
            self.refresh_dashboard()

    # ---- 메모 작성 탭 -------------------------------------------------------------
    def _build_editor_tab(self, parent) -> tk.Frame:
        view = tk.Frame(parent, bg=BG)
        view.columnconfigure(0, weight=5, minsize=400, uniform="cols")
        view.columnconfigure(1, weight=7, uniform="cols")
        view.rowconfigure(0, weight=1)
        left = tk.Frame(view, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        self._build_editor(left)
        self._build_history(left)
        self.report_view = ReportView(view, self.root, self.fonts, "인수인계 보고서",
                                      "메모를 입력하고 ‘보고서 생성’을 누르세요",
                                      "긴급도와 요약, 발생한 일부터 미확인 사항까지 항목별로 정리합니다")
        self.report_view.grid(row=0, column=1, sticky="nsew")
        return view

    def _build_editor(self, parent):
        f = self.fonts
        card = Card(parent)
        card.grid(row=0, column=0, sticky="nsew")
        _, actions = card_header(card, f, "작업 메모", "교대 시 남길 내용을 그대로 적거나 붙여넣으세요")

        self.sample_button = tk.Menubutton(actions, text="예시 메모  ▾", bg=SURFACE, fg=TEXT, font=f.body,
                                           relief="flat", cursor="hand2", padx=12, pady=6,
                                           highlightthickness=1, highlightbackground=BORDER,
                                           activebackground=SUBTLE)
        self.sample_menu = tk.Menu(self.sample_button, tearoff=False, font=f.body, bg=SURFACE,
                                   activebackground=PRIMARY_SOFT, activeforeground=PRIMARY)
        self.sample_button.configure(menu=self.sample_menu)
        for path in find_memos(self.samples_dir):
            self.sample_menu.add_command(label=path.stem, command=lambda p=path: self._load_file(p))
        self.sample_button.pack(side="right", padx=(8, 0))
        Button(actions, "파일 불러오기", self._choose_file, font=f.body).pack(side="right")

        self.source_chip = tk.Label(card, text="", bg=PRIMARY_SOFT, fg=PRIMARY, font=f.small_bold, padx=10, pady=3)

        footer = tk.Frame(card, bg=SURFACE)
        footer.pack(side="bottom", fill="x", padx=20, pady=(12, 18))
        self.count_label = tk.Label(footer, text="0자", bg=SURFACE, fg=FAINT, font=f.small)
        self.count_label.pack(side="left")
        self.generate_button = Button(footer, "보고서 생성", self.generate, kind="primary", font=f.body_bold)
        self.generate_button.pack(side="right")
        tk.Label(footer, text="Ctrl + Enter", bg=SURFACE, fg=FAINT, font=f.small).pack(side="right", padx=10)
        Button(footer, "지우기", self.clear_memo, kind="ghost", font=f.body).pack(side="right")

        wrap = tk.Frame(card, bg=SURFACE)
        wrap.pack(fill="both", expand=True, padx=20)
        self.memo = tk.Text(wrap, wrap="word", undo=True, font=f.editor, bg=SUBTLE, fg=TEXT, relief="flat",
                            padx=14, pady=12, spacing1=2, spacing3=4, insertbackground=PRIMARY,
                            highlightthickness=1, highlightbackground=BORDER, highlightcolor=PRIMARY)
        self.memo.pack(fill="both", expand=True)
        self.placeholder = tk.Label(self.memo, bg=SUBTLE, fg=FAINT, font=f.editor, justify="left", anchor="nw",
                                    text="예) 08:40 포장 2호기 라벨이 자꾸 비뚤어짐.\n"
                                         "09:10 센서 주변 청소하고 재가동.\n"
                                         "원인은 아직 모름. 오후조에서 다시 확인 필요.")
        self.placeholder.bind("<Button-1>", lambda e: self.memo.focus_set())
        self.memo.bind("<<Modified>>", self._on_memo_change)
        self._update_placeholder()

    def _build_history(self, parent):
        f = self.fonts
        card = Card(parent)
        card.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
        _, actions = card_header(card, f, "최근 보고서", "선택하면 저장된 보고서를 다시 볼 수 있습니다")
        Button(actions, "폴더 열기", self._open_folder, kind="ghost", font=f.body).pack(side="right")
        box = tk.Frame(card, bg=SURFACE)
        box.pack(fill="both", expand=True, padx=12, pady=(0, 14))
        self.history_list = tk.Listbox(box, height=6, font=f.body, bg=SURFACE, fg=TEXT, relief="flat", bd=0,
                                       highlightthickness=0, activestyle="none", selectbackground=PRIMARY_SOFT,
                                       selectforeground=PRIMARY)
        self.history_list.pack(fill="both", expand=True, padx=8)
        self.history_list.bind("<<ListboxSelect>>", self._on_history_select)
        self.history_empty = tk.Label(box, text="아직 생성한 보고서가 없습니다", bg=SURFACE, fg=FAINT, font=f.small)

    def status_text(self) -> str:
        return self.report_view.status_text()

    def _memo_text(self) -> str:
        return self.memo.get("1.0", "end-1c")

    def _on_memo_change(self, _event=None):
        self.memo.edit_modified(False)
        self._update_placeholder()

    def _update_placeholder(self):
        text = self._memo_text()
        self.count_label.configure(text=f"{len(text.strip())}자")
        if text:
            self.placeholder.place_forget()
        else:
            self.placeholder.place(x=15, y=13)

    def load_memo_text(self, text: str, name: str):
        self.memo.delete("1.0", "end")
        self.memo.insert("1.0", text.strip())
        self._source_name = name
        self._source_stem = Path(name).stem
        self.source_chip.configure(text=f"불러온 메모 · {name}")
        self.source_chip.pack(anchor="w", padx=20, pady=(0, 8), before=self.memo.master)
        self._update_placeholder()

    def clear_memo(self):
        self.memo.delete("1.0", "end")
        self._source_name, self._source_stem = "직접 입력", "입력"
        self.source_chip.pack_forget()
        self._update_placeholder()
        self.memo.focus_set()

    def _choose_file(self):
        path = filedialog.askopenfilename(title="메모 파일 불러오기", initialdir=self.samples_dir,
                                          filetypes=[("텍스트 메모", "*.txt"), ("모든 파일", "*.*")])
        if path:
            self._load_file(Path(path))

    def _load_file(self, path: Path):
        try:
            self.load_memo_text(read_memo_file(path), path.name)
        except (UnicodeDecodeError, OSError):
            messagebox.showerror("불러오기 실패", f"파일을 읽지 못했습니다.\n{path}\n\nUTF-8 또는 CP949 텍스트 파일인지 확인하세요.")

    def _get_client(self):
        with self._client_lock:
            if self._client is None:
                self._client = self.client_factory()
            return self._client

    def generate(self):
        if self._busy:
            return
        memo = self._memo_text().strip()
        if not memo:
            self.report_view.set_banner("info", "메모를 입력해주세요.",
                                        ["작업 메모를 적거나 ‘파일 불러오기’로 불러온 뒤 다시 누르세요."])
            self.memo.focus_set()
            return
        self._busy = True
        self.generate_button.configure(text="정리 중…")
        self.generate_button.set_enabled(False)
        self.report_view.set_banner(None)
        self.report_view.show_state("loading")
        name, stem = self._source_name, self._source_stem

        def job():
            try:
                result = generate(memo, name, stem, self._get_client(), self.out_dir)
                self._results.put(("ok", (result, name)))
            except ReportError as e:
                self._results.put(("error", str(e)))
            except OSError as e:
                self._results.put(("error", f"보고서를 저장하지 못했습니다: {e}"))

        self.runner(job)
        self.root.after(100, self._poll_loop)

    # ---- 대시보드 탭 --------------------------------------------------------------
    def _build_dashboard_tab(self, parent) -> tk.Frame:
        f = self.fonts
        view = tk.Frame(parent, bg=BG)

        toolbar = Card(view)
        toolbar.pack(fill="x")
        self.folder_label, actions = card_header(toolbar, f, "일괄 처리", "")
        self._update_folder_label()
        self.batch_button = Button(actions, "전체 처리", self.run_batch, kind="primary", font=f.body_bold)
        self.batch_button.pack(side="right", padx=(12, 0))
        self.skip_var = tk.BooleanVar(value=True)
        tk.Checkbutton(actions, text="이미 처리한 메모 건너뛰기", variable=self.skip_var, bg=SURFACE, fg=TEXT,
                       activebackground=SURFACE, selectcolor=SURFACE, font=f.body, bd=0,
                       highlightthickness=0, cursor="hand2").pack(side="right", padx=(12, 0))
        Button(actions, "폴더 변경", self._choose_batch_folder, font=f.body).pack(side="right")
        progress_row = tk.Frame(toolbar, bg=SURFACE)
        self.progress_row = progress_row  # 일괄 처리를 시작하면 표시
        self.batch_progress = ttk.Progressbar(progress_row, mode="determinate", length=260,
                                              style="Accent.Horizontal.TProgressbar")
        self.batch_progress.pack(side="left")
        self.batch_status = tk.Label(progress_row, text="", bg=SURFACE, fg=MUTED, font=f.small, anchor="w",
                                     justify="left")
        self.batch_status.pack(side="left", padx=12, fill="x", expand=True)

        tiles = tk.Frame(view, bg=BG)
        tiles.pack(fill="x", pady=12)
        self._tile_values: dict[str, tk.Label] = {}
        tile_specs = [("전체", TEXT, "처리된 메모"), ("긴급", PRIORITY_COLORS["긴급"][0], "교대 직후 바로 조치"),
                      ("주의", PRIORITY_COLORS["주의"][0], "근무 중 확인 필요"),
                      ("일반", PRIORITY_COLORS["일반"][0], "마감·기록용"),
                      ("경고", "#B45309", "자동 점검 경고가 있는 건"), ("실패", "#B91C1C", "최근 일괄 처리 실패")]
        for i, (key, color, hint) in enumerate(tile_specs):
            tiles.columnconfigure(i, weight=1, uniform="tiles")
            tile = Card(tiles)
            tile.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 12, 0))
            tk.Frame(tile, bg=color, height=3).pack(fill="x")
            tk.Label(tile, text=key, bg=SURFACE, fg=MUTED, font=f.small_bold).pack(anchor="w", padx=16, pady=(8, 0))
            value = tk.Label(tile, text="0", bg=SURFACE, fg=color, font=f.stat)
            value.pack(anchor="w", padx=16)
            tk.Label(tile, text=hint, bg=SURFACE, fg=FAINT, font=f.small).pack(anchor="w", padx=16, pady=(0, 8))
            self._tile_values[key] = value

        row = tk.Frame(view, bg=BG)
        row.pack(fill="x", pady=(0, 12))
        row.columnconfigure(0, weight=3, uniform="insrow")
        row.columnconfigure(1, weight=2, uniform="insrow")
        self._build_insights_card(row).grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        self._build_chart_card(row).grid(row=0, column=1, sticky="nsew")

        main = tk.Frame(view, bg=BG)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=6, uniform="dash")
        main.columnconfigure(1, weight=5, uniform="dash")
        main.rowconfigure(0, weight=1)

        table = Card(main)
        table.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        card_header(table, f, "처리 현황", "긴급 → 주의 → 일반 순으로 정렬됩니다. 행을 선택하면 오른쪽에 상세 보고서가 열립니다")
        box = tk.Frame(table, bg=SURFACE)
        box.pack(fill="both", expand=True, padx=12, pady=(0, 14))
        columns = ("priority", "memo", "summary", "unconfirmed", "warnings", "time")
        self.tree = ttk.Treeview(box, columns=columns, show="headings", style="Dash.Treeview", selectmode="browse")
        for col, heading, width, anchor, stretch in (
                ("priority", "긴급도", 76, "center", False), ("memo", "메모", 150, "w", False),
                ("summary", "요약", 160, "w", True), ("unconfirmed", "미확인", 64, "center", False),
                ("warnings", "경고", 56, "center", False), ("time", "처리 시각", 100, "center", False)):
            self.tree.heading(col, text=heading, anchor=anchor)
            self.tree.column(col, width=width, anchor=anchor, stretch=stretch)
        for priority, (accent, tint) in PRIORITY_COLORS.items():
            self.tree.tag_configure(priority, background=tint if priority != "일반" else SURFACE)
        scroll = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview, style="Slim.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_dashboard_select)
        self.dashboard_empty = tk.Label(box, text="아직 처리한 메모가 없습니다.\n‘전체 처리’를 눌러 폴더의 메모를 한 번에 정리하세요.",
                                        bg=SURFACE, fg=FAINT, font=f.body, justify="center")

        self.detail_view = ReportView(main, self.root, self.fonts, "상세 보고서",
                                      "목록에서 메모를 선택하세요", "선택한 건의 긴급도·요약·항목별 내용이 여기에 표시됩니다")
        self.detail_view.grid(row=0, column=1, sticky="nsew")
        return view

    # ---- AI 인사이트 ----------------------------------------------------------------
    INSIGHT_COLUMNS = (("patterns", "공통 패턴", "#2563EB"), ("risks", "주의할 경향", "#DC2626"),
                       ("gaps", "기록 보완점", "#D97706"))

    # ---- 차트: 미확인 항목이 많은 메모 ------------------------------------------------
    CHART_LIMIT = 8
    CHART_ROW = 30
    # 긴급도는 '상태'이므로 dataviz 상태 팔레트(critical/serious/good)를 쓰고, 항상 글자 라벨과 함께 표시한다.
    STATUS_COLORS = {"긴급": "#D03B3B", "주의": "#EC835A", "일반": "#0CA30C"}

    def _build_chart_card(self, parent) -> tk.Frame:
        f = self.fonts
        card = Card(parent)
        head = tk.Frame(card, bg=SURFACE)
        head.pack(fill="x", padx=20, pady=(14, 2))
        tk.Label(head, text="미확인 항목이 많은 메모", bg=SURFACE, fg=TEXT, font=f.title).pack(side="left")
        legend = tk.Frame(head, bg=SURFACE)
        legend.pack(side="right")
        for name, color in self.STATUS_COLORS.items():
            tk.Frame(legend, bg=color, width=10, height=10).pack(side="left", padx=(10, 4))
            tk.Label(legend, text=name, bg=SURFACE, fg=MUTED, font=f.small).pack(side="left")
        tk.Label(card, text=f"다음 근무자가 직접 확인할 것이 많은 순 · 상위 {self.CHART_LIMIT}건 · 막대를 누르면 상세 보고서",
                 bg=SURFACE, fg=MUTED, font=f.small, anchor="w").pack(fill="x", padx=20)
        self.chart = tk.Canvas(card, bg=SURFACE, highlightthickness=0,
                               height=self.CHART_LIMIT * self.CHART_ROW + 12)
        self.chart.pack(fill="both", expand=True, padx=20, pady=(8, 14))
        self.chart.bind("<Configure>", lambda e: self._draw_chart())
        self._chart_tip = None
        self._chart_bar_count = 0
        return card

    def chart_bars(self) -> int:
        return self._chart_bar_count

    def _draw_chart(self):
        c = self.chart
        c.delete("all")
        f = self.fonts
        rows = unconfirmed_ranking(self._records, self.CHART_LIMIT)
        self._chart_bar_count = len(rows)
        width = max(c.winfo_width(), 320)
        if not rows:
            c.create_text(width / 2, 60, text="미확인 항목이 있는 보고서가 없습니다", fill=FAINT, font=f.body)
            return
        label_w, value_w = 150, 28
        bar_max = max(width - label_w - value_w - 8, 40)
        top = max(n for _, _, n in rows)
        for i, (name, priority, count) in enumerate(rows):
            y = 6 + i * self.CHART_ROW
            mid = y + self.CHART_ROW / 2 - 2
            label = Path(name).stem.replace("작업메모_", "")
            if len(label) > 14:
                label = label[:13] + "…"
            tag = f"bar{i}"
            c.create_text(0, mid, text=f"{priority} · {label}", anchor="w", fill=TEXT, font=f.small, tags=tag)
            x0 = label_w
            x1 = x0 + max(bar_max * count / top, 6)
            color = self.STATUS_COLORS[priority]
            # 얇은 막대(12px), 끝만 둥글게: 사각형 + 끝 원
            c.create_rectangle(x0, mid - 6, x1 - 6, mid + 6, fill=color, outline="", tags=tag)
            c.create_oval(x1 - 12, mid - 6, x1, mid + 6, fill=color, outline="", tags=tag)
            c.create_text(x1 + 6, mid, text=str(count), anchor="w", fill=MUTED, font=f.small_bold, tags=tag)
            # 마우스 영역은 막대보다 넓게 (행 전체)
            hit = c.create_rectangle(0, y, width, y + self.CHART_ROW, fill="", outline="", tags=tag)
            c.tag_lower(hit)
            c.tag_bind(tag, "<Enter>", lambda e, n=name, p=priority, k=count: self._chart_tooltip(e, n, p, k))
            c.tag_bind(tag, "<Leave>", lambda e: self._chart_tooltip(None))
            c.tag_bind(tag, "<Button-1>", lambda e, n=name: self._select_by_name(n))
            c.configure(cursor="hand2")

    def _chart_tooltip(self, event, name=None, priority=None, count=None):
        if self._chart_tip is not None:
            self._chart_tip.destroy()
            self._chart_tip = None
        if event is None:
            return
        record = next((r for r in self._records if r.source_name == name), None)
        summary = record.report.summary if record else ""
        tip = tk.Toplevel(self.root)
        tip.wm_overrideredirect(True)
        tip.configure(bg=HEADER)
        tk.Label(tip, text=f"{name}\n긴급도 {priority} · 미확인 {count}건\n{summary}", bg=HEADER, fg="#FFFFFF",
                 font=self.fonts.small, justify="left", wraplength=320, padx=10, pady=8).pack()
        tip.wm_geometry(f"+{event.x_root + 14}+{event.y_root + 10}")
        self._chart_tip = tip

    def _select_by_name(self, name: str):
        for i, record in enumerate(self._records):
            if record.source_name == name:
                self.tree.see(str(i))
                self.select_dashboard_row(i)
                return

    def _build_insights_card(self, parent) -> tk.Frame:
        f = self.fonts
        card = Card(parent)
        top = tk.Frame(card, bg=SURFACE)
        top.pack(fill="x", padx=20, pady=(14, 6))
        self.insights_button = Button(top, "다시 분석", self.run_insights, font=f.body)
        self.insights_button.pack(side="right")
        self._insights_expanded = False
        self.insights_toggle = Button(top, "자세히 보기", self._toggle_insights, kind="ghost", font=f.body)
        self.insights_toggle.pack(side="right", padx=(0, 8))
        tk.Label(top, text="✦", bg=SURFACE, fg="#7C3AED", font=f.title).pack(side="left")
        tk.Label(top, text=" AI 인사이트", bg=SURFACE, fg=TEXT, font=f.title).pack(side="left")
        self.insights_meta = tk.Label(top, text="", bg=SURFACE, fg=MUTED, font=f.small)
        self.insights_meta.pack(side="left", padx=12)
        self.insights_body = tk.Frame(card, bg=SURFACE)
        self.insights_body.pack(fill="x", padx=20, pady=(0, 14))
        self._insight_labels: list[tk.Label] = []
        return card

    def _insight_label(self, parent, text, **kw) -> tk.Label:
        kw.setdefault("bg", parent["bg"])
        label = tk.Label(parent, text=text, anchor="w", justify="left", **kw)
        self._insight_labels.append(label)
        return label

    def _render_insights(self):
        f = self.fonts
        for child in self.insights_body.winfo_children():
            child.destroy()
        self._insight_labels = []
        snap = self._insight_snapshot
        stale = snap is not None and not snap.is_current(self._records)
        if snap:
            meta = f"보고서 {snap.source_count}건 기준 · {snap.created_at:%m/%d %H:%M} 분석"
            if stale:
                meta += "  ·  이후 보고서가 바뀌었습니다 — 다시 분석하세요"
            self.insights_meta.configure(text=meta, fg="#B45309" if stale else MUTED)
        else:
            self.insights_meta.configure(text="", fg=MUTED)

        if self._insight_message:
            kind, message = self._insight_message
            color = {"loading": PRIMARY, "error": "#B91C1C", "info": MUTED}[kind]
            self._insight_label(self.insights_body, message, fg=color, font=f.body).pack(fill="x", pady=(0, 6))
        if snap is None:
            if not self._insight_message:
                self._insight_label(self.insights_body, "아직 분석한 인사이트가 없습니다. ‘전체 처리’로 보고서를 만들면 "
                                    "Claude가 여러 보고서의 공통점과 주의할 경향을 자동으로 정리합니다.",
                                    fg=FAINT, font=f.body).pack(fill="x")
            return

        self._insight_label(self.insights_body, snap.insights.headline, fg=TEXT, font=f.hero,
                            wraplength=760).pack(fill="x", pady=(0, 10))
        cols = tk.Frame(self.insights_body, bg=SURFACE)
        cols.pack(fill="x")
        for i, (key, title, color) in enumerate(self.INSIGHT_COLUMNS):
            cols.columnconfigure(i, weight=1, uniform="ins")
            col = tk.Frame(cols, bg=SUBTLE, highlightthickness=1, highlightbackground=BORDER)
            col.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 12, 0))
            head = tk.Frame(col, bg=SUBTLE)
            head.pack(fill="x", padx=12, pady=(10, 4))
            tk.Frame(head, bg=color, width=8, height=8).pack(side="left", padx=(0, 6))
            self._insight_label(head, title, fg=TEXT, font=f.body_bold).pack(side="left")
            points = getattr(snap.insights, key)
            shown = points if self._insights_expanded else points[:3]
            if not points:
                self._insight_label(col, "해당 없음", fg=FAINT, font=f.small).pack(fill="x", padx=12, pady=(0, 10))
            for point in shown:
                self._insight_label(col, f"• {point.title}", fg=color, font=f.small_bold,
                                    wraplength=220).pack(fill="x", padx=12, pady=(4, 0))
                if not self._insights_expanded:
                    continue
                self._insight_label(col, point.detail, fg=TEXT, font=f.small, wraplength=220).pack(fill="x", padx=12)
                if point.related:
                    related = ", ".join(Path(n).stem.replace("작업메모_", "") for n in point.related)
                    self._insight_label(col, f"관련: {related}", fg=FAINT, font=f.small,
                                        wraplength=220).pack(fill="x", padx=12)
            if len(points) > len(shown):
                self._insight_label(col, f"외 {len(points) - len(shown)}건", fg=FAINT, font=f.small).pack(fill="x", padx=12)
            tk.Frame(col, bg=SUBTLE, height=8).pack(fill="x")

    def _toggle_insights(self):
        self._insights_expanded = not self._insights_expanded
        self.insights_toggle.configure(text="접기" if self._insights_expanded else "자세히 보기")
        self._render_insights()

    def insights_text(self) -> str:
        return "\n".join(label.cget("text") for label in self._insight_labels
                         if label.winfo_exists()) + "\n" + self.insights_meta.cget("text")

    def run_insights(self):
        if self._insights_busy:
            return
        records = load_records(self.out_dir)
        if not records:
            self._insight_message = ("info", "처리된 보고서가 없습니다 — 먼저 ‘전체 처리’를 실행하세요")
            self._render_insights()
            return
        self._insights_busy = True
        self.insights_button.set_enabled(False)
        self._insight_message = ("loading", f"Claude가 보고서 {len(records)}건의 공통점과 경향을 분석하고 있습니다…")
        self._render_insights()

        def job():
            try:
                insights = extract_insights(records, self._get_client())
                save_insights(self.out_dir, insights, records, datetime.now())
                self._results.put(("insights_ok", None))
            except ReportError as e:
                self._results.put(("insights_error", str(e)))
            except OSError as e:
                self._results.put(("insights_error", f"분석 결과를 저장하지 못했습니다: {e}"))

        self.runner(job)
        self.root.after(100, self._poll_loop)

    def _finish_insights(self, kind, payload):
        self._insights_busy = False
        self.insights_button.set_enabled(True)
        if kind == "insights_ok":
            self._insight_snapshot = load_insights(self.out_dir)
            self._insight_message = None
        else:
            self._insight_message = ("error", f"인사이트를 분석하지 못했습니다 — {payload}")
        self._render_insights()

    def _update_folder_label(self):
        count = len(find_memos(self.batch_folder)) if self.batch_folder.is_dir() else 0
        short = "\\".join(self.batch_folder.parts[-2:])
        self.folder_label.configure(text=f"메모 폴더: …\\{short}  ·  .txt {count}건")

    def _choose_batch_folder(self):
        folder = filedialog.askdirectory(title="메모 폴더 선택", initialdir=self.batch_folder)
        if folder:
            self.batch_folder = Path(folder)
            self._update_folder_label()

    def batch_status_text(self) -> str:
        return self.batch_status.cget("text")

    def run_batch(self):
        if self._batch_busy:
            return
        files = find_memos(self.batch_folder) if self.batch_folder.is_dir() else []
        if not files:
            self.batch_status.configure(text="선택한 폴더에 .txt 메모가 없습니다", fg="#B91C1C")
            self.progress_row.pack(fill="x", padx=20, pady=(0, 16))
            return
        skip = {r.memo_hash for r in load_records(self.out_dir)} if self.skip_var.get() else None
        self._batch_busy = True
        self._batch_total, self._batch_done, self._batch_failed = len(files), 0, []
        self.progress_row.pack(fill="x", padx=20, pady=(0, 16))
        self.batch_button.configure(text="처리 중…")
        self.batch_button.set_enabled(False)
        self.batch_progress.configure(maximum=len(files), value=0)
        self.batch_status.configure(text=f"0/{len(files)} 처리 중 · 최대 4건 동시", fg=MUTED)

        def on_update(item):
            if item.status != "처리 중":
                self._results.put(("batch_item", (item.path.name, item.status, item.message)))

        def job():
            try:
                client = self._get_client()
            except ReportError as e:
                self._results.put(("batch_error", str(e)))
                return
            items = run_batch(files, client, self.out_dir, on_update, skip_hashes=skip)
            self._results.put(("batch_done", items))

        self.runner(job)
        self.root.after(100, self._poll_loop)

    def refresh_dashboard(self):
        self._records = sort_for_dashboard(load_records(self.out_dir))
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(self._records):
            self.tree.insert("", "end", iid=str(i), tags=(r.report.priority,), values=(
                f"● {r.report.priority}", r.source_name, r.report.summary,
                len(r.report.unconfirmed) or "–", len(r.warnings) or "–", f"{r.created_at:%m/%d %H:%M}"))
        if self._records:
            self.dashboard_empty.place_forget()
        else:
            self.dashboard_empty.place(relx=0.5, rely=0.4, anchor="center")
        counts = {"전체": len(self._records), "긴급": 0, "주의": 0, "일반": 0,
                  "경고": sum(1 for r in self._records if r.warnings), "실패": len(self._batch_failed)}
        for r in self._records:
            counts[r.report.priority] += 1
        self._counts = counts
        for key, label in self._tile_values.items():
            label.configure(text=str(counts[key]))
        self._render_insights()
        self._draw_chart()

    def dashboard_rows(self) -> list[tuple]:
        return [(r.report.priority, r.source_name, r.report.summary, r.report.priority_reason,
                 len(r.report.unconfirmed), len(r.warnings)) for r in self._records]

    def tile_counts(self) -> dict[str, int]:
        return dict(self._counts)

    def select_dashboard_row(self, index: int):
        self.tree.selection_set(str(index))
        self._on_dashboard_select()

    def _on_dashboard_select(self, _event=None):
        sel = self.tree.selection()
        if sel:
            self.detail_view.show_record(self._records[int(sel[0])])

    def detail_status_text(self) -> str:
        return self.detail_view.status_text()

    # ---- 결과 처리 ---------------------------------------------------------------
    def _poll_loop(self):
        self.poll_results()
        if self._busy or self._batch_busy or self._insights_busy:
            self.root.after(100, self._poll_loop)

    def poll_results(self):
        while True:
            try:
                kind, payload = self._results.get_nowait()
            except queue.Empty:
                return
            if kind in ("ok", "error"):
                self._finish_single(kind, payload)
            elif kind == "batch_item":
                name, status, message = payload
                self._batch_done += 1
                if status == "실패":
                    self._batch_failed.append(f"{name}: {message}")
                self.batch_progress.configure(value=self._batch_done)
                self.batch_status.configure(
                    text=f"{self._batch_done}/{self._batch_total} 처리 중 · 실패 {len(self._batch_failed)}건", fg=MUTED)
            elif kind in ("insights_ok", "insights_error"):
                self._finish_insights(kind, payload)
            elif kind == "batch_done":
                self._finish_batch(payload)
            elif kind == "batch_error":
                self._batch_busy = False
                self.batch_button.configure(text="전체 처리")
                self.batch_button.set_enabled(True)
                self.batch_status.configure(text=f"일괄 처리를 시작하지 못했습니다 — {payload}", fg="#B91C1C")

    def _finish_single(self, kind, payload):
        self._busy = False
        self.generate_button.configure(text="보고서 생성")
        self.generate_button.set_enabled(True)
        if kind == "ok":
            result, name = payload
            self.report_view.show_report(result.report, result.warnings, name, result.path, result.text)
            self.refresh_history()
            self.refresh_dashboard()
            self.run_insights()  # 새 보고서가 추가됐으니 인사이트도 다시 분석
        else:
            self.report_view.show_state("empty")
            self.report_view.set_banner("error", f"보고서를 만들지 못했습니다 — {payload}",
                                        ["잠시 후 다시 시도하거나, .env의 API 키와 인터넷 연결을 확인하세요."])

    def _finish_batch(self, items):
        self._batch_busy = False
        self.batch_button.configure(text="전체 처리")
        self.batch_button.set_enabled(True)
        done = sum(1 for i in items if i.status == "완료")
        skipped = sum(1 for i in items if i.status == "건너뜀")
        failed = [f"{i.path.name}: {i.message}" for i in items if i.status == "실패"]
        self._batch_failed = failed
        self.batch_progress.configure(value=len(items))
        text = f"완료 {done}건 · 건너뜀 {skipped}건 · 실패 {len(failed)}건"
        if failed:
            text += "\n" + "\n".join(failed[:3]) + (f"\n외 {len(failed) - 3}건" if len(failed) > 3 else "")
        self.batch_status.configure(text=text, fg="#B91C1C" if failed else "#047857")
        self.refresh_dashboard()
        self.refresh_history()
        if done:
            self.run_insights()  # 새 보고서가 생겼으면 공통점을 다시 분석

    # ---- 보고서 이력 --------------------------------------------------------------
    def refresh_history(self):
        paths = sorted(self.out_dir.glob("인수인계_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True) \
            if self.out_dir.is_dir() else []
        self.history_paths = paths
        self.history_list.delete(0, "end")
        for path in paths:
            self.history_list.insert("end", "  " + self._history_label(path))
        if paths:
            self.history_empty.pack_forget()
        else:
            self.history_empty.pack(pady=12)

    @staticmethod
    def _history_label(path: Path) -> str:
        m = _REPORT_NAME.match(path.stem)
        if not m:
            return path.stem
        d, t = m["d"], m["t"]
        return f"{d[4:6]}/{d[6:]} {t[:2]}:{t[2:4]}   {m['stem']}"

    def _on_history_select(self, _event=None):
        sel = self.history_list.curselection()
        if not sel:
            return
        path = self.history_paths[sel[0]]
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            messagebox.showerror("열기 실패", str(e))
            return
        self.report_view.show_text(text, path)

    def _open_folder(self):
        self.out_dir.mkdir(parents=True, exist_ok=True)
        _open_path(self.out_dir)


def _open_path(path: Path):
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 - 사용자가 누른 파일/폴더 열기
    else:
        import subprocess
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


def _make_client():
    key = load_api_key(os.environ)
    if not key:
        raise ReportError(".env에 ANTHROPIC_API_KEY가 없습니다")
    import anthropic
    return anthropic.Anthropic(api_key=key)


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # 고해상도 화면에서 글자가 흐리지 않게
        except (AttributeError, OSError):
            pass
    root = tk.Tk()
    app = HandoverApp(root, client_factory=_make_client, out_dir=BASE_DIR / "reports",
                samples_dir=BASE_DIR / "참고", api_ready=bool(load_api_key(os.environ)))
    if sys.platform == "win32":
        root.state("zoomed")  # 대시보드를 넓게 보도록 최대화로 시작
    root.mainloop()


if __name__ == "__main__":
    main()
