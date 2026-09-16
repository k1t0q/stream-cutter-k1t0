import shutil
import os, sys, re, json, time, math, wave, threading, subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
try:
    import customtkinter as ctk
except ImportError:
    raise SystemExit("Не установлен CustomTkinter. Запустите SETUP_CLIENT.bat один раз.")

BASE=Path(__file__).resolve().parent
RUNTIME=BASE/"runtime"; WORK_ROOT=BASE/"work"; WORK=WORK_ROOT; EXPORTS=BASE/"exports"; MODELS=BASE/"models"
for p in (RUNTIME,WORK_ROOT,EXPORTS,MODELS): p.mkdir(exist_ok=True)
TEST_URL="https://www.youtube.com/live/pBJyRrmuuII?si=lVbeHoeKWxxrmbGm"

def findexe(name):
    return bundled_exe(name)

def find_ffmpeg_dir():
    ff=bundled_exe("ffmpeg.exe")
    return str(Path(ff).parent) if ff else None

def set_vod_work(video_id):
    global WORK
    safe=re.sub(r"[^A-Za-z0-9_-]+","_",str(video_id or "unknown"))[:80] or "unknown"
    WORK=WORK_ROOT/safe
    WORK.mkdir(parents=True,exist_ok=True)
    return WORK


def run(cmd, timeout=None):
    flags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0
    return subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8",errors="replace",
                          timeout=timeout,creationflags=flags)

def hms(x):
    x=max(0,int(x)); return f"{x//3600:02d}:{(x%3600)//60:02d}:{x%60:02d}"



def bundled_exe(name):
    """Find an executable in the app, runtime, PATH or common winget locations."""
    candidates=[
        BASE/name,
        RUNTIME/name,
        RUNTIME/"bin"/name,
        BASE/"bin"/name,
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    found=shutil.which(name) or shutil.which(name.replace(".exe",""))
    if found:
        return found
    # Common Windows ffmpeg layout inside runtime.
    for base in (RUNTIME, BASE):
        try:
            for c in base.rglob(name):
                if c.is_file():
                    return str(c)
        except Exception:
            pass
    return None

def require_runtime():
    missing=[]
    if not bundled_exe("yt-dlp.exe"): missing.append("yt-dlp.exe")
    if not bundled_exe("ffmpeg.exe"): missing.append("ffmpeg.exe")
    if missing:
        raise RuntimeError("Не найдены компоненты: "+", ".join(missing)+
                           ". Запустите SETUP_CLIENT.bat один раз.")

YTDLP = bundled_exe("yt-dlp.exe") or bundled_exe("yt-dlp")

def clean_vod_title(text):
    if not text: return text
    parts=[x for x in str(text).split() if not x.startswith("!")]
    return " ".join(parts).strip()


def install_clipboard_shortcuts(app):
    def focus_entry():
        w=app.focus_get()
        if w is None: return None
        return w if str(w.winfo_class()) in ("Entry","TEntry","Text") else None
    def paste(e=None):
        w=focus_entry()
        if not w: return
        try: text=app.clipboard_get()
        except: return "break"
        try:
            try: w.delete("sel.first","sel.last")
            except: pass
            w.insert("insert",text)
        except: pass
        return "break"
    def select_all(e=None):
        w=focus_entry()
        if not w: return
        try:
            w.selection_range(0,"end"); w.icursor("end")
        except: pass
        return "break"
    app.bind_all("<Control-v>",paste,add="+")
    app.bind_all("<Control-V>",paste,add="+")
    app.bind_all("<Shift-Insert>",paste,add="+")
    app.bind_all("<Control-a>",select_all,add="+")
    app.bind_all("<Control-A>",select_all,add="+")

class ProgressAdapter:
    def __init__(self, bar):
        self.bar=bar
    def __setitem__(self,key,value):
        if key=="value":
            try:
                value=max(0.0,min(100.0,float(value)))
            except Exception:
                value=0.0
            self.value=value
            try: self.widget.set(value/100.0)
            except Exception: pass
            try:
                if hasattr(self.owner,"progress_pct"):
                    self.owner.progress_pct.set(f"{int(round(value))}%")
            except Exception: pass
        else:
            setattr(self,key,value)

    def __getitem__(self,key):
        if key=="value":
            try:return self.bar.get()*100
            except:return 0
        raise KeyError(key)
    def set(self,value):
        self.bar.set(value)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("STREAM CUTTER k1t0 — v1.1.2 RANGE FETCH V2")
        self.geometry("1180x820"); self.minsize(1060,760); self.configure(bg="#0d0d12")
        self.meta=None; self.candidates=[]; self.build()
        self.after(250, lambda: install_clipboard_shortcuts(self))

    def build(self):
        # PREMIUM UI — CustomTkinter shell. Stable analysis/render engine stays unchanged.
        ctk.set_appearance_mode("dark")
        BG="#080b12"; CARD="#111622"; CARD2="#0d121c"; INPUT="#171e2b"
        BORDER="#263044"; TEXT="#f5f7ff"; MUTED="#8f9bb3"; PURPLE="#6c4cff"; PURPLE_H="#7a5cff"
        GREEN="#54d98c"

        self.configure(fg_color=BG)
        self.geometry("1440x920")
        self.minsize(1120,700)

        # Native Treeview is retained only for the data grid; everything else is CustomTkinter.
        st=ttk.Style(self); st.theme_use("clam")
        st.configure("Premium.Treeview",background="#0c111b",fieldbackground="#0c111b",
                     foreground="#e8ecf6",rowheight=42,borderwidth=0,font=("Segoe UI",11))
        st.configure("Premium.Treeview.Heading",background="#171e2b",foreground="#cbd3e4",
                     font=("Segoe UI Semibold",10),relief="flat",padding=(7,8))
        st.map("Premium.Treeview",background=[("selected",PURPLE)],foreground=[("selected","white")])

        main=ctk.CTkFrame(self,fg_color="transparent")
        main.pack(fill="both",expand=True,padx=24,pady=18)

        # Header
        header=ctk.CTkFrame(main,fg_color="transparent",height=52)
        header.pack(fill="x",pady=(0,8))
        header.pack_propagate(False)
        brand=ctk.CTkFrame(header,fg_color="transparent")
        brand.pack(side="left",fill="y")
        ctk.CTkLabel(brand,text="STREAM CUTTER",font=ctk.CTkFont("Segoe UI",29,"bold"),
                     text_color=TEXT).pack(side="left",pady=(7,0))
        ctk.CTkLabel(brand,text="k1t0",font=ctk.CTkFont("Segoe UI",20,"bold"),
                     text_color="#9a7cff").pack(side="left",padx=(8,0),pady=(10,0))
        ctk.CTkLabel(brand,text="AI Shorts Studio",font=ctk.CTkFont("Segoe UI",12),
                     text_color=MUTED).pack(side="left",padx=(18,0),pady=(14,0))

        self.status=tk.StringVar(value="ГОТОВ")
        status_box=ctk.CTkFrame(header,fg_color="transparent")
        status_box.pack(side="right",pady=(8,0))
        ctk.CTkLabel(status_box,text="●",text_color=GREEN,font=ctk.CTkFont(size=13)).pack(side="left")
        ctk.CTkLabel(status_box,textvariable=self.status,text_color=MUTED,
                     font=ctk.CTkFont("Segoe UI",12)).pack(side="left",padx=(6,0))

        # Source card
        source=ctk.CTkFrame(main,fg_color=CARD,corner_radius=14,border_width=1,border_color=BORDER)
        source.pack(fill="x",pady=(0,9))
        top=ctk.CTkFrame(source,fg_color="transparent")
        top.pack(fill="x",padx=18,pady=(12,7))
        ctk.CTkLabel(top,text="ВИДЕО",font=ctk.CTkFont("Segoe UI",16,"bold"),text_color=TEXT).pack(side="left")
        ctk.CTkLabel(top,text="Вставьте ссылку на YouTube и найдите лучшие моменты",
                     font=ctk.CTkFont("Segoe UI",12),text_color=MUTED).pack(side="left",padx=(16,0))

        row=ctk.CTkFrame(source,fg_color="transparent")
        row.pack(fill="x",padx=18)
        self.url=tk.StringVar(value="")
        self.url_entry=ctk.CTkEntry(row,textvariable=self.url,height=48,corner_radius=10,
                                    fg_color=INPUT,border_color=BORDER,border_width=1,
                                    text_color=TEXT,placeholder_text="Вставьте ссылку на YouTube...",
                                    placeholder_text_color="#707b91",font=ctk.CTkFont("Segoe UI",12))
        self.url_entry.pack(side="left",fill="x",expand=True)
        self.install_windows_entry_shortcuts(self.url_entry)
        btn_kw=dict(height=48,corner_radius=10,font=ctk.CTkFont("Segoe UI",12,"bold"))
        ctk.CTkButton(row,text="ВСТАВИТЬ",command=self.paste_url,width=142,
                      fg_color="#202838",hover_color="#2a3549",**btn_kw).pack(side="left",padx=(10,0))
        ctk.CTkButton(row,text="ПРОВЕРИТЬ",command=self.check,width=142,
                      fg_color="#202838",hover_color="#2a3549",**btn_kw).pack(side="left",padx=(8,0))
        ctk.CTkButton(row,text="НАЙТИ МОМЕНТЫ",command=self.analyze,width=170,
                      fg_color=PURPLE,hover_color=PURPLE_H,**btn_kw).pack(side="left",padx=(8,0))

        opts=ctk.CTkFrame(source,fg_color="transparent")
        opts.pack(fill="x",padx=18,pady=(10,10))
        self.test_mode=tk.BooleanVar(value=False)
        ctk.CTkCheckBox(opts,text="Анализировать отрезок",variable=self.test_mode,width=165,
                        checkbox_width=20,checkbox_height=20,corner_radius=5,
                        fg_color=PURPLE,hover_color=PURPLE_H,border_color="#536079",
                        text_color="#dce2ef",font=ctk.CTkFont("Segoe UI",12)).pack(side="left")
        ctk.CTkLabel(opts,text="Начало",text_color=MUTED).pack(side="left",padx=(18,6))
        self.test_start=tk.StringVar(value="00:00:00")
        ctk.CTkOptionMenu(opts,variable=self.test_start,
                          values=["00:00:00","00:15:00","00:30:00","00:45:00","01:00:00",
                                  "01:30:00","02:00:00","03:00:00","04:00:00","05:00:00",
                                  "06:00:00","08:00:00","10:00:00"],
                          width=118,height=38,corner_radius=8,fg_color=INPUT,
                          button_color="#263148",button_hover_color="#34415d",
                          text_color=TEXT).pack(side="left")
        ctk.CTkLabel(opts,text="Длительность",text_color=MUTED).pack(side="left",padx=(16,6))
        self.test_minutes=tk.StringVar(value="30")
        ctk.CTkOptionMenu(opts,variable=self.test_minutes,
                          values=["5","10","15","20","30","45","60","90","120","180"],
                          width=82,height=38,corner_radius=8,fg_color=INPUT,
                          button_color="#263148",button_hover_color="#34415d",
                          text_color=TEXT).pack(side="left")
        ctk.CTkLabel(opts,text="мин",text_color=MUTED).pack(side="left",padx=(5,18))
        ctk.CTkLabel(opts,text="Субтитры",text_color=MUTED).pack(side="left",padx=(0,6))
        self.subtitle_mode=tk.StringVar(value="Динамические")
        ctk.CTkOptionMenu(opts,variable=self.subtitle_mode,values=["Динамические","По словам","Выкл."],
                          width=160,height=38,corner_radius=8,fg_color=INPUT,button_color="#263148",
                          button_hover_color="#34415d",text_color=TEXT).pack(side="left")
        ctk.CTkLabel(opts,text="Макет",text_color=MUTED).pack(side="left",padx=(18,6))
        self.layout_mode=tk.StringVar(value="Авто")
        ctk.CTkOptionMenu(opts,variable=self.layout_mode,values=["Авто","С вебкой","Без вебки"],
                          width=140,height=38,corner_radius=8,fg_color=INPUT,button_color="#263148",
                          button_hover_color="#34415d",text_color=TEXT).pack(side="left")

        self.vod_label=tk.StringVar(value="Видео не выбрано")
        ctk.CTkLabel(source,textvariable=self.vod_label,text_color=MUTED,
                     font=ctk.CTkFont("Segoe UI",12)).pack(anchor="w",padx=18,pady=(0,12))

        # Progress card
        progress_card=ctk.CTkFrame(main,fg_color=CARD2,corner_radius=12,border_width=1,border_color=BORDER)
        progress_card.pack(fill="x",pady=(0,12))
        pr=ctk.CTkFrame(progress_card,fg_color="transparent")
        pr.pack(fill="x",padx=16,pady=(10,4))
        self.info=tk.StringVar(value="Готов к анализу")
        ctk.CTkLabel(pr,textvariable=self.info,text_color="#cbd3e4",
                     font=ctk.CTkFont("Segoe UI",12)).pack(side="left")
        self.progress_text=tk.StringVar(value="0%")
        ctk.CTkLabel(pr,textvariable=self.progress_text,text_color=MUTED).pack(side="right")
        self.pb=ctk.CTkProgressBar(progress_card,height=8,corner_radius=8,
                                   fg_color="#202838",progress_color=PURPLE)
        self.pb.pack(fill="x",padx=16,pady=(4,12)); self.pb.set(0)
        self.pb=ProgressAdapter(self.pb,self)

        # Quick Short
        quick=ctk.CTkFrame(main,fg_color=CARD,corner_radius=14,border_width=1,border_color=BORDER)
        quick.pack(side="bottom",fill="x",pady=(8,0))
        q=ctk.CTkFrame(quick,fg_color="transparent"); q.pack(fill="x",padx=16,pady=9)
        ctk.CTkLabel(q,text="БЫСТРЫЙ SHORT",font=ctk.CTkFont("Segoe UI",16,"bold"),text_color=TEXT).pack(side="left")
        ctk.CTkLabel(q,text="От",text_color=MUTED).pack(side="left",padx=(24,6))
        self.manual_start=tk.StringVar(value="00:25:00")
        ms=ctk.CTkEntry(q,textvariable=self.manual_start,width=92,height=36,corner_radius=7,
                        fg_color=INPUT,border_color=BORDER,text_color=TEXT,justify="center")
        ms.pack(side="left"); self.install_windows_entry_shortcuts(ms)
        ctk.CTkLabel(q,text="До",text_color=MUTED).pack(side="left",padx=(12,6))
        self.manual_end=tk.StringVar(value="00:25:30")
        me=ctk.CTkEntry(q,textvariable=self.manual_end,width=92,height=36,corner_radius=7,
                        fg_color=INPUT,border_color=BORDER,text_color=TEXT,justify="center")
        me.pack(side="left"); self.install_windows_entry_shortcuts(me)
        ctk.CTkButton(q,text="СОЗДАТЬ SHORT",command=self.make_manual_short,width=170,height=38,
                      corner_radius=8,fg_color=PURPLE,hover_color=PURPLE_H,
                      font=ctk.CTkFont("Segoe UI",12,"bold")).pack(side="left",padx=(14,0))
        self.exact_bounds=tk.BooleanVar(value=True)
        ctk.CTkSwitch(q,text="Точные границы",variable=self.exact_bounds,
                      progress_color=PURPLE,text_color=MUTED,
                      font=ctk.CTkFont("Segoe UI",11)).pack(side="left",padx=(16,0))

        # Bottom action cards
        actions=ctk.CTkFrame(main,fg_color="transparent")
        actions.pack(side="bottom",fill="x",pady=(8,0))
        action_kw=dict(height=58,corner_radius=11,font=ctk.CTkFont("Segoe UI",12,"bold"),
                       fg_color="#171e2b",hover_color="#222c3d",border_width=1,border_color=BORDER)
        ctk.CTkButton(actions,text="SHORT ИЗ ВЫБРАННОГО\nСоздать из найденного момента",command=self.make_short,width=260,**action_kw).pack(side="left")
        ctk.CTkButton(actions,text="ВЕБКА\nНастроить область камеры",command=self.calibrate_webcam,width=190,**action_kw).pack(side="left",padx=(10,0))
        ctk.CTkButton(actions,text="ЭКСПОРТЫ\nОткрыть готовые Shorts",command=lambda:self.open(EXPORTS),width=190,**action_kw).pack(side="left",padx=(10,0))


        # Main result area: table + preview placeholder
        work=ctk.CTkFrame(main,fg_color="transparent")
        work.pack(fill="both",expand=True)
        work.grid_columnconfigure(0,weight=1)
        work.grid_rowconfigure(0,weight=1)

        results=ctk.CTkFrame(work,fg_color=CARD,corner_radius=14,border_width=1,border_color=BORDER)
        results.grid(row=0,column=0,sticky="nsew")
        rh=ctk.CTkFrame(results,fg_color="transparent")
        rh.pack(fill="x",padx=16,pady=(13,9))
        ctk.CTkLabel(rh,text="НАЙДЕННЫЕ МОМЕНТЫ",font=ctk.CTkFont("Segoe UI",16,"bold"),
                     text_color=TEXT).pack(side="left")
        self.moment_count=tk.StringVar(value="0")
        ctk.CTkLabel(rh,textvariable=self.moment_count,width=28,height=24,corner_radius=12,
                     fg_color=PURPLE,text_color="white").pack(side="left",padx=(9,0))
        ctk.CTkLabel(rh,text="Выберите строку для создания Short",
                     text_color=MUTED,font=ctk.CTkFont("Segoe UI",12)).pack(side="right")

        table_wrap=ctk.CTkFrame(results,fg_color="#0c111b",corner_radius=9)
        table_wrap.pack(fill="both",expand=True,padx=12,pady=(0,12))
        cols=("score","start","end","dur","reason")
        self.tree=ttk.Treeview(table_wrap,columns=cols,show="headings",style="Premium.Treeview")
        for c,t,w in [("score","SCORE",75),("start","НАЧАЛО",92),("end","КОНЕЦ",92),
                      ("dur","ДЛИТ.",72),("reason","ПОЧЕМУ ЭТО МОМЕНТ",760)]:
            self.tree.heading(c,text=t)
            self.tree.column(c,width=w,anchor="w" if c=="reason" else "center")
        sb=ctk.CTkScrollbar(table_wrap,command=self.tree.yview,width=12,
                            fg_color="#0c111b",button_color="#2b3448",button_hover_color=PURPLE)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right",fill="y",padx=(0,4),pady=4)
        self.tree.pack(side="left",fill="both",expand=True,padx=(4,0),pady=4)


    def load_saved_candidates(self):
        p=WORK/"candidates.json"
        if not p.exists():
            self.info.set("Готов. Сохранённых TOP-моментов нет — при необходимости запусти AI АНАЛИЗ.")
            return
        try:
            data=json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data,list) or not data:
                raise ValueError("candidates.json пуст")
            self.candidates=data
            self.fill(data)
            has_words=False
            tp=WORK/"transcript.json"
            if tp.exists():
                try:
                    td=json.loads(tp.read_text(encoding="utf-8"))
                    has_words=any(x.get("words") for x in td if isinstance(x,dict))
                except: pass
            if has_words:
                self.info.set(f"✓ Загружено {len(data)} TOP-моментов • WORD SYNC готов.")
            else:
                self.info.set(f"✓ {len(data)} TOP-моментов загружено • для ТОЧНОГО WORD SYNC нужен 1 новый AI-анализ.")
            self.pb["value"]=100
        except Exception as e:
            self.info.set(f"Не удалось загрузить candidates.json: {e}")

    def open(self,p):
        if os.name=="nt": os.startfile(p)
    def set_progress(self,pct,status=None):
        self.pb["value"]=pct
        if status is not None:
            self.info.set(status)

    def bg(self,fn): threading.Thread(target=fn,daemon=True).start()

    def activate_meta_project(self,meta):
        self.meta=meta
        vid=str(meta.get("id") or "unknown")
        set_vod_work(vid)
        self.vod_label.set(f'VOD-проект: {vid} • {meta.get("title","VOD")}')
        self.candidates=[]
        for row in self.tree.get_children(): self.tree.delete(row)
        self.load_saved_candidates()
        return vid

    def check(self):
        global YTDLP
        YTDLP = bundled_exe("yt-dlp.exe") or bundled_exe("yt-dlp")
        if not YTDLP:
            messagebox.showerror("STREAM CUTTER","Не найден yt-dlp. Запустите SETUP_CLIENT.bat один раз.")
            return

        def job():
            try:
                self.info.set("Получаю данные VOD…"); self.pb["value"]=20
                r=run([YTDLP,"--dump-single-json","--skip-download","--no-warnings",self.url.get().strip()],120)
                if r.returncode: raise RuntimeError(r.stderr or r.stdout)
                meta=json.loads(r.stdout); self.activate_meta_project(meta); d=int(meta.get("duration") or 0)
                self.pb["value"]=100
                self.info.set(f'✓ {self.meta.get("title","VOD")} • {hms(d)} • готов к audio-only анализу')
            except Exception as e:
                self.pb["value"]=0; messagebox.showerror("STREAM CUTTER",str(e))
        self.bg(job)

    def ensure_whisper(self):
        try:
            import faster_whisper
            return True
        except Exception:
            return False

    def paste_url(self):
        try:
            text=self.clipboard_get().strip()
            if text:
                self.url_entry.delete(0,"end"); self.url_entry.insert(0,text)
                self.url_entry.focus_set(); self.info.set("✓ Ссылка вставлена.")
        except tk.TclError:
            messagebox.showinfo("STREAM CUTTER","В буфере обмена нет текста.")

    def install_windows_entry_shortcuts(self, widget):
        return

    def parse_hms(self, value):
        parts=[int(x) for x in value.strip().split(":")]
        if len(parts)==3: return parts[0]*3600+parts[1]*60+parts[2]
        if len(parts)==2: return parts[0]*60+parts[1]
        return parts[0]

    def analyze(self):
        global YTDLP
        YTDLP = bundled_exe("yt-dlp.exe") or bundled_exe("yt-dlp")
        if not YTDLP:
            messagebox.showerror("STREAM CUTTER","Не найден yt-dlp. Запустите SETUP_CLIENT.bat один раз.")
            return

        for _x in getattr(self,"tree",[]).get_children() if hasattr(getattr(self,"tree",None),"get_children") else []:
            self.tree.delete(_x)
        self.pb["value"]=0
        def job():
            try:
                if not self.ensure_whisper():
                    raise RuntimeError("Не установлен AI-модуль Faster-Whisper.\n\n"
                                       "Закрой программу и один раз запусти INSTALL_AI.bat.\n"
                                       "После установки снова запусти run.bat.")
                from faster_whisper import WhisperModel
                if not self.meta:
                    r=run([YTDLP,"--dump-single-json","--skip-download","--no-warnings",self.url.get().strip()],120)
                    if r.returncode: raise RuntimeError(r.stderr)
                    self.activate_meta_project(json.loads(r.stdout))
                else:
                    # Ensure WORK matches the URL/meta even after switching links.
                    self.activate_meta_project(self.meta)
                self.pb["value"]=10
                is_test=bool(self.test_mode.get())
                if is_test:
                    start_sec=self.parse_hms(self.test_start.get())
                    mins=max(5,int(int(self.test_minutes.get())))
                    end_sec=start_sec+mins*60
                    audio=WORK/f"test_audio_{start_sec}_{end_sec}.m4a"
                    analysis_offset=start_sec
                    analysis_limit=mins*60

                    if audio.exists() and audio.stat().st_size>256*1024:
                        self.info.set(f"✓ FAST CACHE: {mins} мин уже готовы {hms(start_sec)}–{hms(end_sec)}")
                    else:
                        ffdir=find_ffmpeg_dir()
                        if not ffdir:
                            raise RuntimeError("FFmpeg не найден. Запусти INSTALL_FFMPEG.bat.")
                        ffexe=str(Path(ffdir)/"ffmpeg.exe")
                        if not Path(ffexe).exists(): ffexe="ffmpeg"

                        # RANGE FETCH V2: let yt-dlp + ffmpeg request the selected window as ONE job.
                        # No manual 5-minute chunks, no parallel Googlevideo connections and no retry loop.
                        self.info.set(f"Получаю аудио выбранного отрезка • {hms(start_sec)}–{hms(end_sec)}…")
                        self.pb["value"]=18

                        temp_base=WORK/f"range_audio_{start_sec}_{end_sec}"
                        for old in WORK.glob(temp_base.name+".*"):
                            try: old.unlink()
                            except: pass

                        section=f"*{hms(start_sec)}-{hms(end_sec)}"
                        cmd=[YTDLP,"--no-playlist","--no-warnings",
                             "--socket-timeout","30","--retries","5","--fragment-retries","5",
                             "-f","bestaudio[ext=m4a]/bestaudio",
                             "--download-sections",section,
                             "--force-keyframes-at-cuts",
                             "--newline","--progress",
                             "-o",str(temp_base)+".%(ext)s",self.url.get().strip()]
                        flags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0
                        proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                              text=True,encoding="utf-8",errors="replace",
                                              bufsize=1,creationflags=flags)
                        last=[]
                        for line in proc.stdout:
                            line=line.strip()
                            if line:
                                last.append(line)
                                last=last[-25:]
                            m=re.search(r"\[download\]\s+([0-9.]+)%",line)
                            if m:
                                try:
                                    dp=max(0.0,min(100.0,float(m.group(1))))
                                    self.pb["value"]=18+0.10*dp
                                    self.info.set(f"Получаю аудио выбранного отрезка • {dp:.0f}%")
                                    self.update_idletasks()
                                except: pass
                        rc=proc.wait()
                        downloaded=[x for x in WORK.glob(temp_base.name+".*")
                                    if x.is_file() and x.stat().st_size>64*1024]
                        if rc!=0 or not downloaded:
                            raise RuntimeError("YouTube не отдал выбранный аудио-отрезок.\n"+"\n".join(last[-12:]))

                        src_audio=max(downloaded,key=lambda x:x.stat().st_size)
                        # Normalize to tiny mono 16 kHz AAC for Whisper/ACTION ENGINE.
                        rr=run([ffexe,"-hide_banner","-loglevel","error","-y","-i",str(src_audio),
                                "-vn","-ac","1","-ar","16000","-c:a","aac","-b:a","48k",str(audio)],180)
                        if rr.returncode or not audio.exists() or audio.stat().st_size<128*1024:
                            raise RuntimeError("Не удалось подготовить аудио для анализа.\n"+
                                               (rr.stderr or rr.stdout or "")[-2500:])
                        if src_audio != audio:
                            try: src_audio.unlink()
                            except: pass
                        mb=audio.stat().st_size/1024/1024
                        self.info.set(f"✓ RANGE FETCH готов: {mins} мин • {mb:.1f} MB → запускаю Whisper")
                        self.pb["value"]=28
                else:
                    cached=sorted(WORK.glob("vod_audio.*"))
                    if cached and cached[0].stat().st_size>1024*1024:
                        audio=cached[0]
                        self.info.set(f"✓ Использую сохранённое полное аудио ({audio.stat().st_size/1024/1024:.0f} МБ).")
                    else:
                        audio=WORK/"vod_audio.m4a"
                        self.info.set("Получаю полную аудиодорожку VOD…")
                        cmd=[YTDLP,"-f","bestaudio[ext=m4a]/bestaudio","--no-playlist","-o",str(audio),self.url.get().strip()]
                        r=run(cmd,7200)
                        if r.returncode or not audio.exists(): raise RuntimeError((r.stderr or r.stdout)[-3500:])
                    analysis_offset=0
                    analysis_limit=float(self.meta.get("duration") or 1)
                self.pb["value"]=35
                self.info.set(f"Аудио теста готово ({audio.stat().st_size/1024/1024:.0f} МБ). Проверяю GPU…")
                # CUDA can fail only when inference actually begins, so force one segment.
                device="RTX / CUDA"
                try:
                    self.info.set("Проверяю RTX/CUDA реальным тестом распознавания…")
                    model=WhisperModel("small",device="cuda",compute_type="float16",download_root=str(MODELS))
                    test_segments,_=model.transcribe(str(audio),language="ru",vad_filter=True,beam_size=1,
                                                     word_timestamps=False,condition_on_previous_text=False)
                    test_iter=iter(test_segments)
                    try: next(test_iter)
                    except StopIteration: pass
                except Exception:
                    device="CPU"
                    self.info.set("CUDA-библиотеки неполные — автоматически продолжаю на CPU…")
                    model=WhisperModel("small",device="cpu",compute_type="int8",download_root=str(MODELS))
                self.status.set(f"Whisper: small • {device}")
                self.pb["value"]=45
                segments,info=model.transcribe(str(audio),language="ru",vad_filter=True,beam_size=3,
                                               word_timestamps=True,condition_on_previous_text=False)
                segs=[]
                duration=float(getattr(info,"duration",0) or analysis_limit or 1)
                whisper_started=time.time()
                for i,s in enumerate(segments):
                    text=(s.text or "").strip()
                    if text:
                        word_rows=[]
                    for w in (getattr(s,"words",None) or []):
                        wt=str(getattr(w,"word","") or "").strip()
                        if wt:
                            word_rows.append({"start":float(w.start)+analysis_offset,
                                              "end":float(w.end)+analysis_offset,
                                              "word":wt})
                    segs.append({"start":float(s.start)+analysis_offset,"end":float(s.end)+analysis_offset,
                                 "text":text,"words":word_rows})
                    if i%20==0:
                        pos=float(s.end); self.pb["value"]=45+min(40,40*pos/duration)
                        wpct=min(100,100*pos/max(1,duration))
                        self.info.set(f"AI АНАЛИЗ • {hms(pos)} / {hms(duration)} • {wpct:.0f}% • {device} • прошло {hms(time.time()-whisper_started)}")
                        self.update_idletasks()
                (WORK/"transcript.json").write_text(json.dumps(segs,ensure_ascii=False,indent=2),encoding="utf-8")
                self.pb["value"]=86
                self.info.set("ACTION ENGINE • ищу перестрелки и резкие игровые события…")
                action_bins=self.analyze_action_audio(audio,duration)

                # analyze_action_audio works in local time of the downloaded fragment.
                # Shift its bins back onto the original VOD timeline.
                if analysis_offset:
                    for b in action_bins:
                        b["t"]=float(b.get("t",0))+analysis_offset

                self.pb["value"]=92
                self.info.set(f"ACTION ENGINE • найдено {len(action_bins)} аудио-зон • строю кандидаты…")
                cand=self.rank(segs,
                               (analysis_offset+duration if analysis_offset else duration),
                               action_bins=action_bins)
                (WORK/"candidates.json").write_text(json.dumps(cand,ensure_ascii=False,indent=2),encoding="utf-8")
                self.candidates=cand
                self.after(0,lambda:self.fill(cand))
                self.pb["value"]=100
                self.info.set(f"✓ Готово: найдено {len(cand)} моментов • ACTION ENGINE + Whisper {device}")
            except Exception as e:
                self.pb["value"]=0; messagebox.showerror("STREAM CUTTER",str(e))
        self.bg(job)

    def analyze_action_audio(self,audio_path,duration):
        """Cheap CPU combat detector: short-window energy + transient density.
        It does not pretend to know a kill yet; it finds likely firefights/explosions
        so speech-only ranking cannot dominate."""
        import wave, struct, math, subprocess, tempfile
        ffdir=find_ffmpeg_dir()
        ffexe=str(Path(ffdir)/"ffmpeg.exe") if ffdir else "ffmpeg"
        wav=WORK/"action_audio_16k.wav"
        rr=run([ffexe,"-hide_banner","-loglevel","error","-y","-i",str(audio_path),
                "-vn","-ac","1","-ar","16000","-c:a","pcm_s16le",str(wav)],180)
        if rr.returncode or not wav.exists(): return []
        try:
            with wave.open(str(wav),"rb") as w:
                rate=w.getframerate(); frames=w.getnframes()
                raw=w.readframes(frames)
            vals=struct.unpack("<%dh"%(len(raw)//2),raw)
            win=max(1,int(rate*0.25))
            energies=[]
            for i in range(0,len(vals),win):
                chunk=vals[i:i+win]
                if not chunk: break
                rms=math.sqrt(sum(float(x)*x for x in chunk)/len(chunk))/32768.0
                peak=max(abs(x) for x in chunk)/32768.0
                energies.append((rms,peak))
            if not energies:return []
            rms_sorted=sorted(x[0] for x in energies)
            base=rms_sorted[int(len(rms_sorted)*0.60)]
            hot=[]
            # 5 sec bins: gunfire tends to create repeated sharp transients, not one loud word.
            per=max(1,int(5/0.25))
            for bi in range(0,len(energies),per):
                e=energies[bi:bi+per]
                if not e:continue
                loud=sum(1 for rms,pk in e if rms>max(base*1.65,0.025))
                trans=sum(1 for rms,pk in e if pk>max(0.30,base*7.0))
                avg=sum(x[0] for x in e)/len(e)
                score=loud*2.0+trans*2.7+min(10,avg/max(base,0.002))
                hot.append({"t":(bi/per)*5+2.5,"audio_action":score,
                            "transients":trans,"loud":loud})
            return hot
        except Exception:
            return []

    def rank(self,segs,duration,action_bins=None):
        # ACTION ENGINE V1: gameplay audio is primary, speech/reaction is secondary.
        import math
        action_bins=action_bins or []
        emo_words=["бля","блять","сука","пизд","оху","еба","ёба","нихуя","нихера",
                   "жесть","капец","да ладно","вау","ого","ахах","хаха"]
        combat_words=["убил","убили","убил его","попал","попали","выстрел","стреля",
                      "гранат","взорв","снайпер","справа","слева","лежит","нок","минус",
                      "двое","трое","чел","игрок","пуш","раш","зажал","очеред"]
        def text_features(text):
            t=(text or "").lower()
            return sum(w in t for w in emo_words),sum(w in t for w in combat_words),t.count("!")+t.count("?")

        # Build hot-zone centers from audio. Consecutive hot bins merge into a firefight.
        if action_bins:
            vals=sorted(x["audio_action"] for x in action_bins)
            threshold=vals[max(0,int(len(vals)*0.78)-1)]
            threshold=max(threshold,8.0)
            active=[x for x in action_bins if x["audio_action"]>=threshold]
        else: active=[]

        zones=[]
        for x in active:
            if not zones or x["t"]-zones[-1]["end"]>12:
                zones.append({"start":x["t"]-2.5,"end":x["t"]+2.5,"peak":x["t"],
                              "audio":x["audio_action"],"trans":x["transients"]})
            else:
                z=zones[-1]; z["end"]=x["t"]+2.5
                z["audio"]+=x["audio_action"]; z["trans"]+=x["transients"]
                if x["audio_action"]>z.get("peak_score",0):
                    z["peak"]=x["t"]; z["peak_score"]=x["audio_action"]

        # Fallback speech peaks only if audio found too few zones.
        if len(zones)<3:
            speech_peaks=[]
            for sg in segs:
                t=(sg["start"]+sg["end"])/2
                near=[q for q in segs if q["end"]>=t-8 and q["start"]<=t+8]
                txt=" ".join(q.get("text","") for q in near)
                emo,combat,punc=text_features(txt)
                sc=combat*9+emo*4+punc*2+min(8,len(txt.split())/10)
                speech_peaks.append((sc,t))
            for sc,t in sorted(speech_peaks,reverse=True):
                if sc<8:continue
                if any(abs(t-z["peak"])<45 for z in zones):continue
                zones.append({"start":t-2.5,"end":t+2.5,"peak":t,"audio":0,"trans":0,"speech_fallback":True})
                if len(zones)>=8:break

        candidates=[]
        for z in zones:
            peak=max(0,min(duration,z["peak"]))
            # SMART LENGTH: 30–60 sec, based on the actual action-zone span.
            # Short bursts stay compact; longer firefights get more setup/reaction.
            zone_start=max(0,z.get("start",peak-2.5))
            zone_end=min(duration,z.get("end",peak+2.5))
            action_span=max(5.0,zone_end-zone_start)
            target=max(30.0,min(60.0,action_span+24.0))

            # Bias a little more time after the action peak for streamer reaction.
            before=target*0.43
            after=target-before
            st=max(0.0,peak-before)
            en=min(duration,peak+after)

            # Preserve target length near the beginning/end of the VOD.
            if en-st<target:
                if st<=0:
                    en=min(duration,target)
                elif en>=duration:
                    st=max(0.0,duration-target)

            # Hard product limits requested for Shorts.
            if en-st<30:
                st=max(0.0,min(st,duration-30.0))
                en=min(duration,st+30.0)
            if en-st>60:
                en=st+60.0
            ss=[q for q in segs if q["end"]>=st and q["start"]<=en]
            txt=" ".join(q.get("text","") for q in ss)
            emo,combat,punc=text_features(txt)

            # Audio action dominates. Speech can confirm a kill/reaction but cannot win alone.
            audio_strength=min(35,z.get("audio",0)*0.45)
            transient_strength=min(22,z.get("trans",0)*2.2)
            combat_strength=min(20,combat*5)
            reaction_strength=min(24,emo*5+punc*2)
            combo_bonus=8 if (z.get("audio",0)>0 and (emo or punc)) else 0
            score=int(min(99,20+audio_strength+transient_strength+combat_strength+reaction_strength+combo_bonus))
            why=[]
            if z.get("trans",0)>=3: why.append("🔥 серия резких игровых звуков")
            elif z.get("audio",0)>0: why.append("🔥 высокая игровая аудио-активность")
            if combat: why.append("🎯 боевой контекст в речи")
            if emo or punc: why.append("⚡ сильная реакция стримера")
            if z.get("speech_fallback"): why.append("речевой резерв")
            candidates.append({"score":score,"start":round(st,2),"end":round(en,2),
                               "duration":int(round(en-st)),"reason":" + ".join(why) or "ACTION HOT ZONE",
                               "text":txt[:300],"peak":round(peak,2),
                               "action_audio":round(z.get("audio",0),1),
                               "transients":z.get("trans",0)})

        candidates.sort(key=lambda x:x["score"],reverse=True)
        final=[]
        if not candidates:
            return final

        # No arbitrary TOP-7 limit. Keep moments that are strong relative to this VOD.
        # A strong VOD can therefore return many Shorts; a weak one only a few.
        best=candidates[0]["score"]
        quality_floor=max(48, best-26)
        for x in candidates:
            if x["score"] < quality_floor:
                continue
            # Suppress near-duplicates, but do not cap the total count.
            if any(abs(x["peak"]-y["peak"]) < max(30, min(x["duration"],y["duration"])*0.72)
                   for y in final):
                continue
            final.append(x)

        # MULTI-MOMENT: build AI montage candidates from separated strong events.
        # Each montage is 30–60 sec total and consists of short 8–18 sec fragments.
        mixes=[]
        pool=sorted(final,key=lambda q:q["score"],reverse=True)
        used_sets=set()
        for anchor in pool[:6]:
            chosen=[anchor]
            for q in pool:
                if q is anchor: continue
                if any(abs(q["peak"]-z["peak"])<55 for z in chosen): continue
                chosen.append(q)
                if len(chosen)>=4: break
            if len(chosen)<2: continue
            chosen=sorted(chosen,key=lambda q:q["peak"])
            key=tuple(round(q["peak"]) for q in chosen)
            if key in used_sets: continue
            used_sets.add(key)

            # Give stronger events slightly more screen time.
            clips=[]; total=0.0
            for q in chosen:
                clip_len=max(9.0,min(16.0,9.0+(q["score"]-quality_floor)*0.22))
                a=max(0.0,q["peak"]-clip_len*0.42)
                b=min(duration,q["peak"]+clip_len*0.58)
                if b-a<8: continue
                clips.append({"start":round(a,2),"end":round(b,2),"peak":q["peak"],
                              "score":q["score"],"reason":q["reason"]})
                total+=b-a
                if total>=46: break
            if len(clips)<2: continue
            # Expand the last clip with reaction tail when montage is under 30 sec.
            if total<30:
                extra=min(30-total,8)
                clips[-1]["end"]=round(min(duration,clips[-1]["end"]+extra),2)
                total=sum(c["end"]-c["start"] for c in clips)
            if total>60:
                overflow=total-60
                clips[-1]["end"]=round(max(clips[-1]["start"]+8,clips[-1]["end"]-overflow),2)
                total=sum(c["end"]-c["start"] for c in clips)

            mix_score=int(round(sum(c["score"] for c in clips)/len(clips)+min(6,len(clips)*1.5)))
            mixes.append({"score":min(99,mix_score),"start":clips[0]["start"],
                          "end":clips[-1]["end"],"duration":int(round(total)),
                          "reason":f"AI MIX • {len(clips)} сильных фрагмента • динамичная нарезка",
                          "text":"","peak":clips[0]["peak"],"multi":True,"clips":clips})
            if len(mixes)>=3: break

        return mixes + final

    def fill(self,c):
        for x in self.tree.get_children(): self.tree.delete(x)
        self.row_candidates={}
        self.moment_count.set(str(len(c)))
        for x in c:
            if x.get("multi"):
                vals=(x["score"],"AI MIX",f'{len(x.get("clips",[]))} фрагм.',
                      f'{x["duration"]} сек',x["reason"])
            else:
                vals=(x["score"],hms(x["start"]),hms(x["end"]),
                      f'{x["duration"]} сек',x["reason"])
            iid=self.tree.insert("", "end",values=vals)
            self.row_candidates[iid]=x
    def selected_times(self):
        sel=self.tree.selection()
        if not sel:
            raise RuntimeError("Выбери строку TOP-момента в таблице.")
        vals=self.tree.item(sel[0],"values")
        cand=getattr(self,"row_candidates",{}).get(sel[0])
        if cand and cand.get("multi"):
            return vals,float(cand["start"]),float(cand["end"])
        return vals,self.parse_hms(str(vals[1])),self.parse_hms(str(vals[2]))

    def source_for_times(self,start,end):
        cut_start=max(0,start-3); cut_end=end+2
        hits=sorted(WORK.glob(f"source_{cut_start}_{cut_end}.*"))
        return (hits[0] if hits else None),cut_start,cut_end

    def calibrate_webcam(self):
        try:
            vals,start,end=self.selected_times()
        except Exception as e:
            return messagebox.showinfo("STREAM CUTTER",str(e))
        def job():
            try:
                src,cut_start,cut_end=self.source_for_times(start,end)
                ffdir=find_ffmpeg_dir()
                if not ffdir: raise RuntimeError("FFmpeg не найден.")
                if not src:
                    self.set_progress(5,"Для калибровки скачиваю SOURCE выбранного момента…")
                    src=WORK/f"source_{cut_start}_{cut_end}.mp4"
                    section=f"*{hms(cut_start)}-{hms(cut_end)}"
                    cmd=[YTDLP,"--ffmpeg-location",ffdir,"-f","bv*+ba/b","--merge-output-format","mp4",
                         "--download-sections",section,"--force-keyframes-at-cuts","-o",str(src),self.url.get().strip()]
                    r=run(cmd,1800)
                    if r.returncode or not src.exists():
                        hits=sorted(WORK.glob(f"source_{cut_start}_{cut_end}.*"))
                        if hits: src=hits[0]
                        else: raise RuntimeError((r.stderr or r.stdout or "Не удалось получить SOURCE")[-3500:])
                ffexe=str(Path(ffdir)/"ffmpeg.exe")
                if not Path(ffexe).exists(): ffexe="ffmpeg"
                frame=WORK/"webcam_calibration.png"
                r=run([ffexe,"-hide_banner","-loglevel","error","-y","-ss","5","-i",str(src),
                       "-frames:v","1","-vf","scale=960:-2",str(frame)],120)
                if r.returncode or not frame.exists(): raise RuntimeError(r.stderr or "Не удалось получить кадр.")
                self.after(0,lambda:self.show_calibration(frame,src))
            except Exception as e:
                self.after(0,lambda:messagebox.showerror("STREAM CUTTER",str(e)))
        self.bg(job)

    def show_calibration(self,frame,src):
        win=tk.Toplevel(self); win.title("КАЛИБРОВКА ВЕБКИ — обведи вебку мышкой")
        img=tk.PhotoImage(file=str(frame))
        canvas=tk.Canvas(win,width=img.width(),height=img.height(),cursor="cross")
        canvas.pack(); canvas.create_image(0,0,image=img,anchor="nw"); canvas.image=img
        state={"x":0,"y":0,"rect":None,"box":None}
        def down(e):
            state["x"],state["y"]=e.x,e.y
            if state["rect"]: canvas.delete(state["rect"])
            state["rect"]=canvas.create_rectangle(e.x,e.y,e.x,e.y,outline="red",width=3)
        def move(e):
            if state["rect"]: canvas.coords(state["rect"],state["x"],state["y"],e.x,e.y)
        def up(e):
            x1,x2=sorted((state["x"],e.x)); y1,y2=sorted((state["y"],e.y))
            state["box"]=(x1,y1,x2,y2)
        canvas.bind("<Button-1>",down); canvas.bind("<B1-Motion>",move); canvas.bind("<ButtonRelease-1>",up)
        bar=ttk.Frame(win,padding=8); bar.pack(fill="x")
        ttk.Label(bar,text="Обведи ТОЛЬКО область вебки. Это сохранится для всех Shorts этого стрима.").pack(side="left")
        def savebox():
            if not state["box"]: return messagebox.showinfo("STREAM CUTTER","Сначала обведи вебку.")
            x1,y1,x2,y2=state["box"]
            if x2-x1<30 or y2-y1<30: return messagebox.showinfo("STREAM CUTTER","Область слишком маленькая.")
            # frame was scaled to width 960; save normalized coordinates
            cfg={"x":x1/img.width(),"y":y1/img.height(),"w":(x2-x1)/img.width(),"h":(y2-y1)/img.height()}
            (WORK/"webcam_profile.json").write_text(json.dumps(cfg,indent=2),encoding="utf-8")
            self.info.set("✓ Вебка откалибрована. Теперь можно создавать Short.")
            win.destroy()
        ttk.Button(bar,text="✓ СОХРАНИТЬ ВЕБКУ",command=savebox).pack(side="right")

    def censor_subtitle(self,text):
        # Visual-only censorship: audio is untouched.
        # Covers common Russian profanity stems and typical Whisper variants.
        rules=[
            (r"(?iu)\bбл(?:я|е)[тд][ьъ]?\w*", "б***ь"),
            (r"(?iu)\bбля\w*", "б***ь"),
            (r"(?iu)\bхуй\w*", "х**"),
            (r"(?iu)\bху[яеёию]\w*", "х**"),
            (r"(?iu)\bпизд\w*", "п***"),
            (r"(?iu)\bеб(?:а|у|и|ё|е|л|н|т)\w*", "е***"),
            (r"(?iu)\bёб\w*", "ё***"),
            (r"(?iu)\bзаеб\w*", "з***"),
            (r"(?iu)\bнаеб\w*", "н***"),
            (r"(?iu)\bоху\w*", "о***"),
            (r"(?iu)\bдолбоеб\w*", "д***"),
        ]
        for pat,repl in rules:
            text=re.sub(pat,repl,text)
        return text

    def subtitle_chunks(self,text,max_chars=26,max_lines=2):
        # Dynamic Shorts-style captions: normally 2–5 words per card.
        words=text.split()
        cards=[]; cur=[]
        for w in words:
            proposal=" ".join(cur+[w])
            if cur and (len(cur)>=5 or len(proposal)>max_chars):
                cards.append(" ".join(cur))
                cur=[w]
            else:
                cur.append(w)
            # Prefer a natural short card once it reaches 3–4 words and is already wide.
            if len(cur)>=3 and len(" ".join(cur))>=20:
                cards.append(" ".join(cur)); cur=[]
        if cur:
            if cards and len(cur)==1:
                cards[-1]+=" "+cur[0]
            else:
                cards.append(" ".join(cur))
        # Last safety net: no card can escape horizontally.
        safe=[]
        for card in cards:
            if len(card)<=max_chars:
                safe.append(card)
            else:
                ws=card.split(); line=""; lines=[]
                for w in ws:
                    t=(line+" "+w).strip()
                    if len(t)<=max_chars: line=t
                    else:
                        if line: lines.append(line)
                        line=w
                if line: lines.append(line)
                safe.append("\\N".join(lines[:max_lines]))
        return safe or [""]
    def make_ass(self,start,end):
        if getattr(self,"subtitle_mode",None) and self.subtitle_mode.get()=="Выкл.":
            return None
        tr=WORK/"transcript.json"
        if not tr.exists(): return None
        try: data=json.loads(tr.read_text(encoding="utf-8"))
        except: return None

        def ts(sec):
            h=int(sec//3600); m=int((sec%3600)//60); ss=sec%60
            return f"{h}:{m:02d}:{ss:05.2f}"

        ass=WORK/"short_subtitles.ass"
        head="""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Short,Arial,58,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,1,2,105,105,260,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
        mode=self.subtitle_mode.get() if getattr(self,"subtitle_mode",None) else "Динамические"
        events=[]
        for seg in data:
            sa=float(seg.get("start",0)); sb=float(seg.get("end",0))
            if sb<=start or sa>=end: continue
            words=[w for w in (seg.get("words") or [])
                   if float(w.get("end",0))>start and float(w.get("start",0))<end]
            if words:
                # Censor each word before grouping. This preserves exact timestamps.
                clean=[]
                for w in words:
                    clean.append({"start":max(start,float(w["start"])),
                                  "end":min(end,float(w["end"])),
                                  "word":self.censor_subtitle(str(w["word"]).strip())})
                if mode=="По словам":
                    groups=[[w] for w in clean]
                else:
                    groups=[]; cur=[]
                    for w in clean:
                        proposal=" ".join(x["word"] for x in cur+[w])
                        if cur and (len(cur)>=5 or len(proposal)>26):
                            groups.append(cur); cur=[w]
                        else:
                            cur.append(w)
                        if len(cur)>=3 and len(" ".join(x["word"] for x in cur))>=20:
                            groups.append(cur); cur=[]
                    if cur:
                        if groups and len(cur)==1 and len(groups[-1])<5: groups[-1].extend(cur)
                        else: groups.append(cur)
                for g in groups:
                    text=" ".join(x["word"] for x in g)
                    a=max(0,g[0]["start"]-start)
                    # Hold card until last spoken word, plus tiny readability tail.
                    b=min(end-start,max(g[-1]["end"]-start,a+0.18)+0.08)
                    if b>a and text:
                        events.append((a,b,text))
            else:
                # Backward compatibility for old transcript.json made before v0.3.5.
                a=max(start,sa); b=min(end,sb)
                text=self.censor_subtitle(str(seg.get("text","")).strip())
                if not text or b<=a: continue
                cards=self.subtitle_chunks(text,26,2)
                total=b-a; weights=[max(1,len(c.split())) for c in cards]; sw=sum(weights)
                cur=a-start
                for i,(card,w) in enumerate(zip(cards,weights)):
                    nxt=(b-start) if i==len(cards)-1 else cur+total*w/sw
                    events.append((cur,nxt,card)); cur=nxt

        if not events: return None
        lines=[]
        for a,b,t in events:
            t=t.replace("\\","").replace("{","(").replace("}",")").replace("\n"," ")
            lines.append(f"Dialogue: 0,{ts(a)},{ts(b)},Short,,0,0,0,,{t}")
        ass.write_text(head+"\n".join(lines),encoding="utf-8-sig")
        return ass

    def make_ass_multi(self,clips):
        """Create word-synced subtitles remapped onto a discontinuous montage timeline."""
        if getattr(self,"subtitle_mode",None) and self.subtitle_mode.get()=="Выкл.": return None
        tr=WORK/"transcript.json"
        if not tr.exists(): return None
        try: data=json.loads(tr.read_text(encoding="utf-8"))
        except: return None
        def ts(sec):
            h=int(sec//3600); m=int((sec%3600)//60); ss=sec%60
            return f"{h}:{m:02d}:{ss:05.2f}"
        events=[]; offset=0.0
        mode=self.subtitle_mode.get() if getattr(self,"subtitle_mode",None) else "Динамические"
        for clip in clips:
            a0=float(clip["start"]); b0=float(clip["end"])
            words=[]
            for seg in data:
                for w in (seg.get("words") or []):
                    ws=float(w.get("start",0)); we=float(w.get("end",0))
                    if we>a0 and ws<b0:
                        words.append({"start":max(a0,ws),"end":min(b0,we),
                                      "word":self.censor_subtitle(str(w.get("word","")).strip())})
            words.sort(key=lambda w:w["start"])
            groups=[]
            if mode=="По словам": groups=[[w] for w in words]
            else:
                cur=[]
                for w in words:
                    proposal=" ".join(x["word"] for x in cur+[w])
                    if cur and (len(cur)>=5 or len(proposal)>26):
                        groups.append(cur); cur=[w]
                    else: cur.append(w)
                    if len(cur)>=3 and len(" ".join(x["word"] for x in cur))>=20:
                        groups.append(cur); cur=[]
                if cur: groups.append(cur)
            for g in groups:
                if not g: continue
                aa=offset+(g[0]["start"]-a0)
                bb=offset+(g[-1]["end"]-a0)+0.08
                text=" ".join(x["word"] for x in g)
                if bb>aa and text: events.append((aa,bb,text))
            offset += b0-a0
        if not events: return None
        ass=WORK/"short_subtitles_multi.ass"
        head="""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Short,Arial,58,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,1,2,105,105,260,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
        lines=[]
        for a,b,t in events:
            t=t.replace("\\","").replace("{","(").replace("}",")").replace("\n"," ")
            lines.append(f"Dialogue: 0,{ts(a)},{ts(b)},Short,,0,0,0,,{t}")
        ass.write_text(head+"\n".join(lines),encoding="utf-8-sig")
        return ass

    def _mix_download_with_progress(self,cmd,out_path,part_no,total_parts,clip_dur):
        """Run yt-dlp and expose visible per-fragment progress in the main UI."""
        import subprocess, time
        proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                              text=True,encoding="utf-8",errors="replace",
                              creationflags=(subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0))
        pct=0.0
        started=time.time()
        while proc.poll() is None:
            # yt-dlp writes to .part while downloading.
            candidates=[out_path,Path(str(out_path)+".part")]
            size=max([x.stat().st_size for x in candidates if x.exists()] or [0])
            # No reliable Content-Length for every YouTube stream; combine transferred
            # bytes + elapsed time into a smooth, non-fake "activity" progress ceiling.
            activity=min(92.0, max(pct, (time.time()-started)/max(12.0,clip_dur*0.8)*72.0))
            if size>0: activity=max(activity,min(92.0,18.0+size/(1024*1024)*3.2))
            pct=activity
            overall=((part_no-1)+pct/100.0)/max(1,total_parts)*82.0
            self.pb["value"]=overall
            mb=size/(1024*1024)
            self.info.set(f"AI MIX • загрузка {part_no}/{total_parts} • {pct:.0f}% • {mb:.1f} MB")
            time.sleep(.35)
        output=proc.stdout.read() if proc.stdout else ""
        return proc.returncode,output

    def make_multi_short(self,cand,vals):
        clips=cand.get("clips") or []
        if len(clips)<2: raise RuntimeError("AI MIX не содержит достаточно фрагментов.")
        profile_path=WORK/"webcam_profile.json"
        layout=getattr(self,"layout_mode",tk.StringVar(value="Авто")).get()
        use_webcam=profile_path.exists() if layout=="Авто" else (layout=="С вебкой")
        if use_webcam and not profile_path.exists():
            raise RuntimeError("Для режима «С вебкой» сначала настройте область камеры.")
        ffdir=find_ffmpeg_dir()
        if not ffdir: raise RuntimeError("FFmpeg не найден.")
        ffexe=str(Path(ffdir)/"ffmpeg.exe")
        if not Path(ffexe).exists(): ffexe="ffmpeg"

        sources=[]
        for i,c in enumerate(clips,1):
            a=float(c["start"]); b=float(c["end"])
            self.info.set(f"AI MIX • получаю фрагмент {i}/{len(clips)} • {hms(a)}–{hms(b)}")
            src=WORK/f"mix_{i}_{int(a)}_{int(b)}.mp4"
            if not src.exists() or src.stat().st_size<128*1024:
                section=f"*{hms(a)}-{hms(b)}"
                dlcmd=[YTDLP,"--ffmpeg-location",ffdir,"--socket-timeout","25",
                       "--retries","3","-f","bv*+ba/b","--merge-output-format","mp4",
                       "--download-sections",section,"--force-keyframes-at-cuts",
                       "-o",str(src),self.url.get().strip()]
                rc,dlout=self._mix_download_with_progress(dlcmd,src,i,len(clips),b-a)
                if rc or not src.exists():
                    hits=sorted(WORK.glob(f"mix_{i}_{int(a)}_{int(b)}.*"))
                    if hits: src=hits[0]
                    else: raise RuntimeError(f"Не удалось получить AI MIX фрагмент {i}.")
            sources.append(src)

        ass=self.make_ass_multi(clips)
        cfg=json.loads(profile_path.read_text(encoding="utf-8")) if use_webcam else None
        parts=[]; concat_inputs=[]
        for i,src in enumerate(sources):
            if use_webcam:
                cx=max(0,min(.98,float(cfg["x"]))); cy=max(0,min(.98,float(cfg["y"])))
                cw=max(.02,min(1-cx,float(cfg["w"]))); ch=max(.02,min(1-cy,float(cfg["h"])))
                parts.append(
                    f"[{i}:v]split=2[c{i}][g{i}];"
                    f"[c{i}]crop=iw*{cw}:ih*{ch}:iw*{cx}:ih*{cy},"
                    f"scale=1080:720:force_original_aspect_ratio=increase,crop=1080:720[c2_{i}];"
                    f"[g{i}]scale=1080:1200:force_original_aspect_ratio=increase,crop=1080:1200[g2_{i}];"
                    f"[c2_{i}][g2_{i}]vstack=inputs=2[v{i}]")
            else:
                parts.append(f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=increase,"
                             f"crop=1080:1920[v{i}]")
            concat_inputs.append(f"[v{i}][{i}:a]")
        parts.append("".join(concat_inputs)+f"concat=n={len(sources)}:v=1:a=1[base][aout]")
        if ass:
            ap=str(ass).replace("\\","/").replace(":","\\:")
            parts.append(f"[base]subtitles='{ap}'[vout]")
        else:
            parts.append("[base]null[vout]")
        filt=";".join(parts)
        vod_exports=EXPORTS/(str(self.meta.get("id") if self.meta else "unknown"))
        vod_exports.mkdir(parents=True,exist_ok=True)
        out=vod_exports/f"SHORT_AI_MIX_{len(clips)}_{cand['score']}.mp4"
        cmd=[ffexe,"-hide_banner","-loglevel","error","-y"]
        for src in sources: cmd += ["-i",str(src)]
        cmd += ["-filter_complex",filt,"-map","[vout]","-map","[aout]",
                "-c:v","libx264","-preset","veryfast","-crf","20","-r","60",
                "-c:a","aac","-b:a","160k","-movflags","+faststart",str(out)]
        self.pb["value"]=88
        self.info.set(f"AI MIX • все фрагменты загружены • собираю Short…")
        self.pb["value"]=92
        r=run(cmd,1800)
        if r.returncode or not out.exists():
            raise RuntimeError((r.stderr or r.stdout or "Ошибка сборки AI MIX")[-4000:])
        self.pb["value"]=100
        self.info.set(f"✓ AI MIX • 100% • готов: {out.name}")
        return out

    def make_manual_short(self):
        """Create a Short from exact user-entered boundaries without AI selection."""
        try:
            start=self.parse_hms(self.manual_start.get().strip())
            end=self.parse_hms(self.manual_end.get().strip())
            if end<=start: raise RuntimeError("Конец должен быть позже начала.")
            if end-start>180: raise RuntimeError("Для ручного Short укажите отрезок до 3 минут.")
            # Insert a temporary row so the proven Short pipeline can be reused.
            iid=self.tree.insert("","end",values=("MANUAL",hms(start),hms(end),f"{int(end-start)} сек","Ручной таймкод"))
            self.tree.selection_set(iid); self.tree.focus(iid); self.tree.see(iid)
            self.make_short()
        except Exception as e:
            messagebox.showerror("STREAM CUTTER",str(e))

    def make_short(self):
        try:
            vals,start,end=self.selected_times()
        except Exception as e:
            return messagebox.showinfo("STREAM CUTTER",str(e))
        sel=self.tree.selection()
        cand=getattr(self,"row_candidates",{}).get(sel[0]) if sel else None
        if cand and cand.get("multi"):
            def mix_job():
                try:
                    out=self.make_multi_short(cand,vals)
                    self.after(0,lambda:messagebox.showinfo("STREAM CUTTER",f"AI MIX готов!\\n\\n{out}"))
                except Exception as e:
                    self.pb["value"]=0
                    self.after(0,lambda:messagebox.showerror("STREAM CUTTER",str(e)))
            self.bg(mix_job)
            return
        profile_path=WORK/"webcam_profile.json"
        layout=getattr(self,"layout_mode",tk.StringVar(value="Авто")).get()
        use_webcam = profile_path.exists() if layout=="Авто" else (layout=="С вебкой")
        if use_webcam and not profile_path.exists():
            return messagebox.showinfo("STREAM CUTTER","Для режима «С вебкой» сначала нажмите «ВЕБКА» и обведите её один раз.")
        # Add context around AI window while keeping a Shorts-friendly duration.
        cut_start=max(0,start-3); cut_end=end+2
        def job():
            try:
                ffdir=find_ffmpeg_dir()
                if not ffdir:
                    raise RuntimeError("FFmpeg не найден.")
                self.info.set(f"Скачиваю только SOURCE {hms(cut_start)}–{hms(cut_end)}…")
                src=WORK/f"source_{cut_start}_{cut_end}.mp4"
                section=f"*{hms(cut_start)}-{hms(cut_end)}"
                cmd=[YTDLP,"--ffmpeg-location",ffdir,
                     "-f","bv*+ba/b","--merge-output-format","mp4",
                     "--download-sections",section,"--force-keyframes-at-cuts",
                     "-o",str(src),self.url.get().strip()]
                r=run(cmd,1800)
                if (r.returncode or not src.exists()):
                    hits=sorted(WORK.glob(f"source_{cut_start}_{cut_end}.*"))
                    if hits: src=hits[0]
                    else: raise RuntimeError((r.stderr or r.stdout or "Не удалось скачать SOURCE")[-4000:])
                self.pb["value"]=70
                self.info.set("SOURCE получен. Собираю вертикальный 1080×1920 Short…")
                vod_exports=EXPORTS/(str(self.meta.get("id") if self.meta else "unknown")); vod_exports.mkdir(parents=True,exist_ok=True)
                out=vod_exports/f"SHORT_{hms(start).replace(':','-')}_{str(vals[0]).lower()}.mp4"
                ffexe=str(Path(ffdir)/"ffmpeg.exe")
                if not Path(ffexe).exists(): ffexe="ffmpeg"

                ass=self.make_ass(cut_start,cut_end)
                if use_webcam:
                    cfg=json.loads(profile_path.read_text(encoding="utf-8"))
                    cx=max(0,min(.98,float(cfg["x"]))); cy=max(0,min(.98,float(cfg["y"])))
                    cw=max(.02,min(1-cx,float(cfg["w"]))); ch=max(.02,min(1-cy,float(cfg["h"])))
                    filt=(
                        f"[0:v]split=2[cam][game];"
                        f"[cam]crop=iw*{cw}:ih*{ch}:iw*{cx}:ih*{cy},"
                        "scale=1080:720:force_original_aspect_ratio=increase,crop=1080:720[cam2];"
                        "[game]scale=1080:1200:force_original_aspect_ratio=increase,crop=1080:1200[game2];"
                        "[cam2][game2]vstack=inputs=2[base]"
                    )
                else:
                    # No webcam: fill the entire 9:16 canvas with gameplay.
                    filt=("[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
                          "crop=1080:1920[base]")
                if ass:
                    ap=str(ass).replace("\\","/").replace(":","\\:")
                    filt += f";[base]subtitles='{ap}'[v]"
                else:
                    filt += ";[base]null[v]"
                cmd=[ffexe,"-hide_banner","-loglevel","error","-y","-i",str(src),
                     "-filter_complex",filt,"-map","[v]","-map","0:a?",
                     "-c:v","libx264","-preset","veryfast","-crf","20","-r","60",
                     "-c:a","aac","-b:a","160k","-movflags","+faststart",str(out)]
                r=run(cmd,1800)
                if r.returncode or not out.exists():
                    raise RuntimeError((r.stderr or r.stdout or "Ошибка сборки Short")[-4000:])
                self.pb["value"]=100
                self.info.set(f"✓ SHORT готов: {out.name}")
                self.after(0,lambda:messagebox.showinfo("STREAM CUTTER",f"SHORT готов!\\n\\n{out}"))
            except Exception as e:
                self.pb["value"]=0
                self.after(0,lambda:messagebox.showerror("STREAM CUTTER",str(e)))
        self.bg(job)

    def save(self):
        p=WORK/"candidates.json"
        if not p.exists(): return messagebox.showinfo("STREAM CUTTER","Сначала запусти AI АНАЛИЗ.")
        dst=EXPORTS/"TOP_MOMENTS.json"; dst.write_bytes(p.read_bytes())
        self.info.set(f"✓ Сохранено: {dst}")

if __name__=="__main__": App().mainloop()
