from pathlib import Path
import time

# 🔹 Автоматически определяем корень проекта (где лежит папка app/)
ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / "app"
OUT_FILE = ROOT / "all_python_sources.txt"
SEP = "\n" + "=" * 80 + "\n"

if not APP_DIR.is_dir():
    print(f"❌ Папка app/ не найдена в {ROOT}")
    exit(1)

# 🔹 Исключаем мусор
IGNORE_DIRS = {"__pycache__", ".venv", "venv", "env", "logs", "tests", ".git"}

py_files = []
for p in APP_DIR.rglob("*.py"):
    parts = p.relative_to(APP_DIR).parts
    if not any(ignore in parts for ignore in IGNORE_DIRS):
        py_files.append(p)

py_files.sort(key=lambda x: x.relative_to(APP_DIR).as_posix())

print(f"📂 Сканирую: {APP_DIR}")
print(f"📄 Найдено файлов: {len(py_files)}")
print(f"💾 Результат: {OUT_FILE}")

with OUT_FILE.open("w", encoding="utf-8") as out:
    for i, p in enumerate(py_files):
        if i > 0:
            out.write(SEP)
        rel = p.relative_to(APP_DIR).as_posix()
        mtime = time.ctime(p.stat().st_mtime)
        out.write(f"# FILE: {rel}\n# MODIFIED: {mtime}\n\n")
        content = p.read_text(encoding="utf-8", errors="replace")
        out.write(content)
        if not content.endswith("\n"):
            out.write("\n")

print("✅ Готово. Файл актуализирован.")