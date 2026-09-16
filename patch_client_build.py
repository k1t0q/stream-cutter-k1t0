from pathlib import Path
import py_compile

p=Path('stream_cutter.py')
s=p.read_text(encoding='utf-8')

# IMPORTANT: PyInstaller onedir stores imported code under _internal, but our
# external runtime folder is beside STREAM CUTTER k1t0.exe. Use sys.executable
# for every bundled-client resource lookup.
s=s.replace('BASE=Path(__file__).resolve().parent', 'BASE=Path(sys.executable).resolve().parent if getattr(sys,"frozen",False) else Path(__file__).resolve().parent')

# ProgressAdapter compatibility for packaged client.
s=s.replace('def __init__(self, bar):\n        self.bar=bar', 'def __init__(self, bar, owner=None):\n        self.bar=bar\n        self.widget=bar\n        self.owner=owner', 1)
s=s.replace('if hasattr(self.owner,"progress_pct"):\n                    self.owner.progress_pct.set(f"{int(round(value))}%")', 'if self.owner is not None:\n                    if hasattr(self.owner,"progress_text"):\n                        self.owner.progress_text.set(f"{int(round(value))}%")\n                    elif hasattr(self.owner,"progress_pct"):\n                        self.owner.progress_pct.set(f"{int(round(value))}%")', 1)

# RANGE FETCH: resolve ffmpeg.exe itself and pass its parent directory directly
# to yt-dlp. This avoids PATH and _internal/runtime ambiguity in frozen builds.
needle='cmd=[YTDLP,"--no-playlist","--no-warnings",\n                             "--socket-timeout","30","--retries","5","--fragment-retries","5",'
replacement='ffmpeg_path=bundled_exe("ffmpeg.exe")\n                        if not ffmpeg_path:\n                            raise RuntimeError("FFmpeg отсутствует в клиентской сборке.")\n                        ffmpeg_location=str(Path(ffmpeg_path).resolve().parent)\n                        cmd=[YTDLP,"--no-playlist","--no-warnings",\n                             "--ffmpeg-location",ffmpeg_location,\n                             "--socket-timeout","30","--retries","5","--fragment-retries","5",'
if needle not in s:
    raise RuntimeError('RANGE FETCH command not found; refusing unpatched build')
s=s.replace(needle,replacement,1)

# Build-time assertions: fail GitHub Actions rather than shipping another bad EXE.
assert '"--ffmpeg-location",ffmpeg_location' in s
assert 'BASE=Path(sys.executable).resolve().parent if getattr(sys,"frozen",False)' in s
s=s.replace('v1.1.2 RANGE FETCH V2', 'v1.1.4 RANGE FETCH PATH FIX')
p.write_text(s, encoding='utf-8')
py_compile.compile(str(p), doraise=True)
print('v1.1.4: frozen BASE + explicit resolved FFmpeg location verified.')
