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
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from handover.config import load_api_key
from handover.files import read_memo_file
from handover.llm import MODEL, ReportError
from handover.service import GenerationResult, generate
from handover.view import EMPTY, build_sections

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

_REPORT_NAME = re.compile(r"^인수인계_(?P<stem>.+)_(?P<d>\d{8})_(?P<t>\d{6})(?:_\d+)?$")


class Fonts:
    def __init__(self, root: tk.Misc):
        families = set(tkfont.families(root))
        base = next((f for f in ("Malgun Gothic", "맑은 고딕", "Apple SD Gothic Neo", "Noto Sans KR")
                     if f in families), "TkDefaultFont")
        mono = next((f for f in ("D2Coding", "Consolas", "Menlo") if f in families), "TkFixedFont")
        self.brand = (base, 15, "bold")
        self.title = (base, 12, "bold")
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
        self.bind("<Leave>", lambda e: self.configure(bg=bg if self._enabled else self["bg"]))
        self.bind("<Button-1>", lambda e: self._enabled and self._command())

    def set_enabled(self, enabled: bool):
        bg, fg, _ = self._colors
        self._enabled = enabled
        self.configure(fg=fg if enabled else FAINT, bg=bg, cursor="hand2" if enabled else "arrow")


class Card(tk.Frame):
    def __init__(self, master, **kw):
        super().__init__(master, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER, **kw)


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


class HandoverApp:
    def __init__(self, root: tk.Tk, client_factory, out_dir: Path, samples_dir: Path,
                 runner=None, api_ready: bool | None = None):
        self.root = root
        self.client_factory = client_factory
        self.out_dir = Path(out_dir)
        self.samples_dir = Path(samples_dir)
        self.runner = runner or (lambda fn: threading.Thread(target=fn, daemon=True).start())
        self.api_ready = api_ready
        self.fonts = Fonts(root)
        self.history_paths: list[Path] = []
        self._results: queue.Queue = queue.Queue()
        self._busy = False
        self._client = None
        self._source_name = "직접 입력"
        self._source_stem = "입력"
        self._current_text = ""
        self._current_path: Path | None = None
        self._banner_text = ""
        self._wrap_labels: list[tk.Label] = []

        self._setup_root()
        self._build_header()
        self._build_body()
        self.refresh_history()
        self._show_state("empty")

    # ---- 레이아웃 --------------------------------------------------------------
    def _setup_root(self):
        self.root.title("교대 인수인계 보고서")
        self.root.configure(bg=BG)
        self.root.geometry("1280x820")
        self.root.minsize(1040, 680)
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
        self.root.bind("<Control-Return>", lambda e: (self.generate(), "break")[1])

    def _build_header(self):
        f = self.fonts
        header = tk.Frame(self.root, bg=HEADER, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)

        brand = tk.Frame(header, bg=HEADER)
        brand.pack(side="left", padx=24)
        logo = tk.Label(brand, text="인", bg=PRIMARY, fg="#FFFFFF", font=f.title, width=2, pady=2)
        logo.pack(side="left", pady=16)
        titles = tk.Frame(brand, bg=HEADER)
        titles.pack(side="left", padx=12)
        tk.Label(titles, text="교대 인수인계", bg=HEADER, fg="#FFFFFF", font=f.brand).pack(anchor="w")
        tk.Label(titles, text="작업 메모를 다음 근무자용 보고서로 정리합니다", bg=HEADER, fg=HEADER_MUTED,
                 font=f.small).pack(anchor="w")

        status = tk.Frame(header, bg=HEADER)
        status.pack(side="right", padx=24)
        if self.api_ready is None:
            dot, label = FAINT, "Claude API"
        elif self.api_ready:
            dot, label = "#34D399", "Claude API 연결 준비됨"
        else:
            dot, label = "#F87171", "API 키 없음 · .env 확인"
        pill = tk.Frame(status, bg="#1E293B", padx=12, pady=5)
        pill.pack(side="right")
        tk.Label(pill, text="●", bg="#1E293B", fg=dot, font=f.small).pack(side="left")
        tk.Label(pill, text=f" {label}", bg="#1E293B", fg="#E2E8F0", font=f.small_bold).pack(side="left")
        tk.Label(pill, text=f"  ·  {MODEL}", bg="#1E293B", fg=HEADER_MUTED, font=f.small).pack(side="left")

    def _build_body(self):
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=20, pady=20)
        body.columnconfigure(0, weight=5, minsize=400, uniform="cols")
        body.columnconfigure(1, weight=7, uniform="cols")
        body.rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        self._build_editor(left)
        self._build_history(left)
        self._build_report(body)

    def _card_header(self, card, title, subtitle):
        head = tk.Frame(card, bg=SURFACE)
        head.pack(fill="x", padx=20, pady=(18, 12))
        text = tk.Frame(head, bg=SURFACE)
        text.pack(side="left", fill="x", expand=True)
        tk.Label(text, text=title, bg=SURFACE, fg=TEXT, font=self.fonts.title).pack(anchor="w")
        sub = tk.Label(text, text=subtitle, bg=SURFACE, fg=MUTED, font=self.fonts.small)
        sub.pack(anchor="w", pady=(2, 0))
        actions = tk.Frame(head, bg=SURFACE)
        actions.pack(side="right")
        return sub, actions

    def _build_editor(self, parent):
        f = self.fonts
        card = Card(parent)
        card.grid(row=0, column=0, sticky="nsew")
        _, actions = self._card_header(card, "작업 메모", "교대 시 남길 내용을 그대로 적거나 붙여넣으세요")

        self.sample_button = tk.Menubutton(actions, text="예시 메모  ▾", bg=SURFACE, fg=TEXT, font=f.body,
                                           relief="flat", cursor="hand2", padx=12, pady=6,
                                           highlightthickness=1, highlightbackground=BORDER,
                                           activebackground=SUBTLE)
        self.sample_menu = tk.Menu(self.sample_button, tearoff=False, font=f.body, bg=SURFACE,
                                   activebackground=PRIMARY_SOFT, activeforeground=PRIMARY)
        self.sample_button.configure(menu=self.sample_menu)
        for path in sorted(self.samples_dir.glob("*.txt")):
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
        _, actions = self._card_header(card, "최근 보고서", "선택하면 저장된 보고서를 다시 볼 수 있습니다")
        Button(actions, "폴더 열기", self._open_folder, kind="ghost", font=f.body).pack(side="right")
        box = tk.Frame(card, bg=SURFACE)
        box.pack(fill="both", expand=True, padx=12, pady=(0, 14))
        self.history_list = tk.Listbox(box, height=6, font=f.body, bg=SURFACE, fg=TEXT, relief="flat", bd=0,
                                       highlightthickness=0, activestyle="none", selectbackground=PRIMARY_SOFT,
                                       selectforeground=PRIMARY)
        self.history_list.pack(fill="both", expand=True, padx=8)
        self.history_list.bind("<<ListboxSelect>>", self._on_history_select)
        self.history_empty = tk.Label(box, text="아직 생성한 보고서가 없습니다", bg=SURFACE, fg=FAINT, font=f.small)

    def _build_report(self, parent):
        f = self.fonts
        card = Card(parent)
        card.grid(row=0, column=1, sticky="nsew")
        self.meta_label, actions = self._card_header(card, "인수인계 보고서", "생성된 보고서가 여기에 표시됩니다")
        self.open_button = Button(actions, "파일 열기", self._open_current, font=f.body)
        self.open_button.pack(side="right", padx=(8, 0))
        self.copy_button = Button(actions, "복사", self._copy_current, font=f.body)
        self.copy_button.pack(side="right")
        self.copy_button.set_enabled(False)
        self.open_button.set_enabled(False)

        self.banner = tk.Frame(card, highlightthickness=1)
        self.banner_icon = tk.Label(self.banner, font=f.body_bold, width=2)
        self.banner_icon.pack(side="left", anchor="n", padx=(12, 4), pady=10)
        self.banner_body = tk.Frame(self.banner)
        self.banner_body.pack(side="left", fill="x", expand=True, pady=10, padx=(0, 12))
        self.banner_anchor = tk.Frame(card, bg=SURFACE, height=0)
        self.banner_anchor.pack(fill="x", padx=20)

        self.content = tk.Frame(card, bg=SURFACE)
        self.content.pack(fill="both", expand=True, padx=20, pady=(8, 20))

        self.empty_state = tk.Frame(self.content, bg=SURFACE)
        inner = tk.Frame(self.empty_state, bg=SURFACE)
        inner.place(relx=0.5, rely=0.45, anchor="center")
        tk.Label(inner, text="📋", bg=SURFACE, fg=FAINT, font=f.icon).pack()
        tk.Label(inner, text="메모를 입력하고 ‘보고서 생성’을 누르세요", bg=SURFACE, fg=TEXT,
                 font=f.title).pack(pady=(10, 4))
        tk.Label(inner, text="발생한 일 · 조치한 내용 · 현재 상태 · 다음 근무자 확인 사항 · 미확인 사항으로 정리합니다",
                 bg=SURFACE, fg=MUTED, font=f.small).pack()

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

    # ---- 상태 전환 ---------------------------------------------------------------
    def _show_state(self, name: str):
        for state in (self.empty_state, self.loading_state, self.result_area, self.text_view):
            state.pack_forget()
        target = {"empty": self.empty_state, "loading": self.loading_state,
                  "result": self.result_area, "text": self.text_view}[name]
        target.pack(fill="both", expand=True)
        if name == "loading":
            self.progress.start(12)
        else:
            self.progress.stop()

    def _set_banner(self, kind: str | None, title: str = "", lines: list[str] | None = None):
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
                 justify="left").pack(fill="x")
        for line in lines or []:
            label = tk.Label(self.banner_body, text=f"• {line}", bg=bg, fg=fg, font=self.fonts.small,
                             anchor="w", justify="left", wraplength=640)
            label.pack(fill="x", pady=(2, 0))
        self.banner.pack(in_=self.banner_anchor, fill="x", pady=(0, 4))
        self.banner.lift(self.banner_anchor)  # anchor보다 나중에 그려야 가려지지 않는다

    def status_text(self) -> str:
        return self._banner_text

    # ---- 메모 입력 ---------------------------------------------------------------
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

    # ---- 보고서 생성 -------------------------------------------------------------
    def generate(self):
        if self._busy:
            return
        memo = self._memo_text().strip()
        if not memo:
            self._set_banner("info", "메모를 입력해주세요.", ["작업 메모를 적거나 ‘파일 불러오기’로 불러온 뒤 다시 누르세요."])
            self.memo.focus_set()
            return
        self._busy = True
        self.generate_button.configure(text="정리 중…")
        self.generate_button.set_enabled(False)
        self._set_banner(None)
        self._show_state("loading")
        name, stem = self._source_name, self._source_stem

        def job():
            try:
                if self._client is None:
                    self._client = self.client_factory()
                result = generate(memo, name, stem, self._client, self.out_dir)
                self._results.put(("ok", result))
            except ReportError as e:
                self._results.put(("error", str(e)))
            except OSError as e:
                self._results.put(("error", f"보고서를 저장하지 못했습니다: {e}"))

        self.runner(job)
        self.root.after(100, self._poll_loop)

    def _poll_loop(self):
        self.poll_results()
        if self._busy:
            self.root.after(100, self._poll_loop)

    def poll_results(self):
        while True:
            try:
                kind, payload = self._results.get_nowait()
            except queue.Empty:
                return
            self._busy = False
            self.generate_button.configure(text="보고서 생성")
            self.generate_button.set_enabled(True)
            if kind == "ok":
                self.show_result(payload)
            else:
                self._show_state("empty")
                self._set_banner("error", f"보고서를 만들지 못했습니다 — {payload}",
                                 ["잠시 후 다시 시도하거나, .env의 API 키와 인터넷 연결을 확인하세요."])

    def show_result(self, result: GenerationResult):
        self._current_text, self._current_path = result.text, result.path
        self.copy_button.set_enabled(True)
        self.open_button.set_enabled(True)
        self.meta_label.configure(text=f"{self._source_name}  ·  저장됨: {result.path.name}")
        if result.warnings:
            self._set_banner("warning", f"자동 점검 경고 {len(result.warnings)}건 — 원문과 대조해 확인하세요",
                             result.warnings)
        else:
            self._set_banner("success", "자동 점검: 이상 없음 — 원문에 없는 숫자·단정 표현이 발견되지 않았습니다")
        self._render_sections(result)
        self._show_state("result")
        self.refresh_history()
        if self.history_paths:
            self.history_list.selection_clear(0, "end")

    def _render_sections(self, result: GenerationResult):
        f = self.fonts
        self.result_area.clear()
        self._wrap_labels = []
        for section in build_sections(result.report):
            accent = ACCENTS[section.kind]
            bg = UNCONFIRMED_BG if section.kind == "unconfirmed" else SURFACE
            outer = tk.Frame(self.result_area.inner, bg=bg, highlightthickness=1,
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

    # ---- 보고서 이력 / 동작 --------------------------------------------------------
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
        self._current_text, self._current_path = text, path
        self.copy_button.set_enabled(True)
        self.open_button.set_enabled(True)
        self.meta_label.configure(text=f"저장된 보고서  ·  {path.name}")
        self._set_banner("info", "저장된 보고서를 보고 있습니다", ["새 보고서를 만들려면 메모를 입력하고 ‘보고서 생성’을 누르세요."])
        self.text_view.configure(state="normal")
        self.text_view.delete("1.0", "end")
        self.text_view.insert("1.0", text)
        self.text_view.configure(state="disabled")
        self._show_state("text")

    def _copy_current(self):
        if not self._current_text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self._current_text)
        self.copy_button.configure(text="복사됨 ✓")
        self.root.after(1500, lambda: self.copy_button.configure(text="복사"))

    def _open_current(self):
        if self._current_path and self._current_path.exists():
            _open_path(self._current_path)

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
    HandoverApp(root, client_factory=_make_client, out_dir=BASE_DIR / "reports",
                samples_dir=BASE_DIR / "참고", api_ready=bool(load_api_key(os.environ)))
    root.mainloop()


if __name__ == "__main__":
    main()
