"""Syntax-check the dashboard's inline JavaScript using Node.js."""
import re
import subprocess
import tempfile
from pathlib import Path

html = Path("index.html").read_text(encoding="utf-8")
scripts = re.findall(r"<script(?:\\s[^>]*)?>(.*?)</script>", html, flags=re.IGNORECASE | re.DOTALL)
if not scripts:
    raise SystemExit("No inline JavaScript block found in index.html")
with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as handle:
    handle.write("\\n".join(scripts))
    handle.flush()
    subprocess.run(["node", "--check", handle.name], check=True)
print(f"Checked JavaScript syntax in {len(scripts)} inline script block(s).")
