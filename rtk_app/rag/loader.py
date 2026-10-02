"""Загрузка документов: txt, md, pdf → текст.

Поддерживаемые форматы:
  - .txt  — текстовые файлы (UTF-8)
  - .md   — Markdown-файлы (UTF-8)
  - .pdf  — PDF с текстовым слоем (pypdf)
"""
import os

__all__ = ["load_file", "load_directory", "SUPPORTED_EXTENSIONS"]

SUPPORTED_EXTENSIONS = (".txt", ".md", ".pdf")


def load_file(filepath):
    """Загружает текст из одного файла.

    Возвращает (success, text, error).
    """
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == ".pdf":
            return _load_pdf(filepath)
        else:
            # .txt, .md
            with open(filepath, "r", encoding="utf-8") as f:
                return True, f.read(), None
    except Exception as exc:
        return False, "", str(exc)


def _load_pdf(filepath):
    """Извлекает текст из PDF через pypdf (только текстовый слой)."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return False, "", "pypdf не установлен"

    try:
        reader = PdfReader(filepath)
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return True, "\n\n".join(pages), None
    except Exception as exc:
        return False, "", str(exc)


def load_directory(directory):
    """Загружает все поддерживаемые файлы из директории.

    Возвращает список dict:
      [
        {
          "path": "full/path/file.txt",
          "name": "file.txt",
          "text": "...",
          "size": 1234,
          "ok": True,
          "error": None,
        },
        ...
      ]
    """
    if not directory or not os.path.isdir(directory):
        return []

    results = []
    for root, dirs, files in os.walk(directory):
        for fname in sorted(files):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue

            fpath = os.path.join(root, fname)
            ok, text, error = load_file(fpath)
            results.append({
                "path": fpath,
                "name": os.path.relpath(fpath, directory),
                "text": text if ok else "",
                "size": os.path.getsize(fpath) if ok else 0,
                "ok": ok,
                "error": error,
            })

    return results
