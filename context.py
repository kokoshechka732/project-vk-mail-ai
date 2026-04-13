from pathlib import Path

ROOT = Path(r"C:\Users\me\Desktop\Project\project-vk-mail-ai\app")
OUT  = ROOT / "all_python_sources.txt"
SEP  = "\n" + ("=" * 80) + "\n"

if not ROOT.exists():
    raise SystemExit(f"Папка не найдена: {ROOT}")

py_files = sorted(p for p in ROOT.rglob("*.py") if p.is_file() and p != OUT)

print(f"Найдено .py файлов: {len(py_files)}")
print(f"Файл результата будет: {OUT}")

with OUT.open("w", encoding="utf-8") as out:
    for i, p in enumerate(py_files):
        if i:
            out.write(SEP)
        out.write(f"# FILE: {p.relative_to(ROOT).as_posix()}\n\n")
        content = p.read_text(encoding="utf-8", errors="replace")
        out.write(content)
        if not content.endswith("\n"):
            out.write("\n")

print("Готово.")