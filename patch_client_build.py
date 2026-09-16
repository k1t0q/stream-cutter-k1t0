from pathlib import Path
import py_compile

p=Path('stream_cutter.py')
s=p.read_text(encoding='utf-8')

# EXE must use the directory containing the executable as BASE.
s=s.replace('BASE=Path(__file__).resolve().parent', 'BASE=Path(sys.executable).resolve().parent if getattr(sys,"frozen",False) else Path(__file__).resolve().parent')

# ProgressAdapter compatibility for the packaged client.
s=s.replace('def __init__(self, bar):\n        self.bar=bar', 'def __init__(self, bar, owner=None):\n        self.bar=bar\n        self.widget=bar\n        self.owner=owner', 1)
s=s.replace('if hasattr(self.owner,"progress_pct"):\n                    self.owner.progress_pct.set(f"{int(round(value))}%")', 'if self.owner is not None:\n                    if hasattr(self.owner,"progress_text"):\n                        self.owner.progress_text.set(f"{int(round(value))}%")\n                    elif hasattr(self.owner,"progress_pct"):\n                        self.owner.progress_pct.set(f"{int(round(value))}%")', 1)

# RANGE FETCH V2 uses yt-dlp --download-sections, which invokes FFmpeg itself.
# In the packaged client FFmpeg lives in runtime/, so explicitly pass that directory.
needle='cmd=[YTDLP,"--no-playlist","--no-warnings",\n                             "--socket-timeout","30","--retries","5","--fragment-retries","5",'
replacement='cmd=[YTDLP,"--no-playlist","--no-warnings",\n                             "--ffmpeg-location",ffdir,\n                             "--socket-timeout","30","--retries","5","--fragment-retries","5",'
if needle not in s:
    raise RuntimeError('RANGE FETCH V2 yt-dlp command not found; refusing to build an unpatched client')
s=s.replace(needle,replacement,1)

s=s.replace('v1.1.2 RANGE FETCH V2', 'v1.1.3 RANGE FETCH FFMPEG FIX')
p.write_text(s, encoding='utf-8')
py_compile.compile(str(p), doraise=True)
print('v1.1.3: bundled FFmpeg path injected into yt-dlp RANGE FETCH and syntax checked.')
