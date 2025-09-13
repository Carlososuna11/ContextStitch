# ContextStitch 🧵

**ContextStitch** concatenates your repository into a single `.md` or `.txt` file that includes:

- A folder **tree** (respecting ignore rules)
- The **contents of each file** (with code fences in Markdown)
- Options to **respect `.gitignore`**, apply **language presets** (e.g., Python), and add your **own ignore patterns**
- Safe handling to skip **binary/large files**

Perfect to generate a compact, ChatGPT‑ready context file for code reviews or Q&A.

---

## ✨ Features

- CLI: `contextstitch [options]`
- Respects `.gitignore` (or a custom one via `--gitignore`)
- Presets: `--preset python` (skips `__pycache__`, virtualenvs, build artifacts, etc.)
- Smart file filtering: skip binaries, huge files, hidden files (configurable)
- Output to `stdout` or a file (`.md` or `.txt`)
- Clear Markdown headings with per-file language detection by extension

---

## 📦 Installation

### From source

```bash
git clone https://github.com/your-user/contextstitch.git
cd contextstitch
pip install -e .        # or: pipx install .
```

> Requires Python 3.8+

---

## 🚀 Usage

```bash
# Basic: write Markdown to a file in the current directory
contextstitch

# Choose format and output path
contextstitch --format md --output repo-context.md

# Respect a specific .gitignore file
contextstitch --gitignore /path/to/.gitignore

# Use Python preset (ignores __pycache__, .venv, build/, dist/, etc.)
contextstitch --preset python

# Include hidden files (off by default)
contextstitch --include-hidden

# Extra ignore patterns (glob/gitignore-style)
contextstitch --ignore '*.log' --ignore 'dist/**' --ignore 'node_modules/**'

# Limit file sizes (default 1 MiB)
contextstitch --max-file-size 500k

# Write to stdout (handy with pipes)
contextstitch --stdout

# Stitch a specific root directory
contextstitch --root /path/to/project
```

### Example: produce a TXT to feed another tool
```bash
contextstitch --format txt --output context.txt --preset python --gitignore .gitignore
```

---

## ⚙️ Options

```
--root PATH               Root directory to stitch (default: .)
--output PATH             Output file path (default: auto-named in CWD) or use --stdout
--stdout                  Print to stdout instead of writing a file
--format {md,txt}         Output format (default: md)
--gitignore PATH          Path to a .gitignore file to respect
--no-gitignore            Do not respect any .gitignore even if present
--preset {python,node}    Language/stack preset for ignores
--ignore PATTERN          Extra ignore pattern(s); can repeat
--include-hidden          Include dotfiles/directories (default: off)
--max-file-size SIZE      Skip files larger than SIZE (e.g., 500k, 2m) default: 1m
--follow-symlinks         Follow symlinks (default: off)
--relative-paths          Use relative paths in output (default) (toggle off to show absolute)
--encoding ENCODING       Default text encoding to try (default: utf-8)
--quiet                   Reduce log output
--version                 Show version and exit
```

> Patterns use `.gitignore` semantics via `pathspec`.

---

## 🛡️ Robustness

- Detects and skips likely **binary** files
- Handles encoding errors by falling back to `'utf-8'` with `errors="replace"`
- Protects against accidental huge outputs via `--max-file-size`

---

## 🧰 Exit Codes

- `0` success
- `1` runtime or invalid-arg error

---

## 🧪 Tests

A tiny smoke test is provided under `tests/`.

Run:
```bash
python -m pytest -q
```

---

## 📝 License

MIT
