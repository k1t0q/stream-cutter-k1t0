from pathlib import Path
import py_compile

p=Path('stream_cutter.py')
s=p.read_text(encoding='utf-8')

# Keep the proven v1.0.9 engine/UI, patch only EXE compatibility + YouTube fetch stability.
s=s.replace('BASE=Path(__file__).resolve().parent', 'BASE=Path(sys.executable).resolve().parent if getattr(sys,"frozen",False) else Path(__file__).resolve().parent')

# ProgressAdapter in v1.0.9 was called with (bar, app) but declared with one arg.
s=s.replace('def __init__(self, bar):\n        self.bar=bar', 'def __init__(self, bar, owner=None):\n        self.bar=bar\n        self.widget=bar\n        self.owner=owner', 1)
s=s.replace('if hasattr(self.owner,"progress_pct"):\n                    self.owner.progress_pct.set(f"{int(round(value))}%")', 'if self.owner is not None:\n                    if hasattr(self.owner,"progress_text"):\n                        self.owner.progress_text.set(f"{int(round(value))}%")\n                    elif hasattr(self.owner,"progress_pct"):\n                        self.owner.progress_pct.set(f"{int(round(value))}%")', 1)

# Old code opened six simultaneous Googlevideo streams for a 30-min range.
# A single early CDN reset then killed all still-running chunks and immediately entered recovery.
# Use at most three analysis chunks and let healthy workers finish before recovering failures.
s=s.replace('chunk_sec=300', 'chunk_sec=max(300, math.ceil((mins*60)/3))', 1)
s=s.replace('if failed:\n                                # A single YouTube/CDN connection can die while the other parallel', 'active=[j for j in jobs if j["proc"] is not None and j["proc"].poll() is None]\n                            if failed and not active:\n                                # Wait for healthy parallel chunks before recovery.\n                                # A single YouTube/CDN connection can die while the other parallel', 1)

s=s.replace('v1.0.9 UNIFIED PROGRESS', 'v1.1.1 CLIENT EXE FETCH FIX')
p.write_text(s, encoding='utf-8')
py_compile.compile(str(p), doraise=True)
print('Client build patch applied and syntax checked.')
