from pathlib import Path

print((Path.cwd() / ".env").read_text())
