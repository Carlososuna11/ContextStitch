from __future__ import annotations

import io
import os
import sys
import stat
import time
import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple

try:
    import pathspec
except ImportError:  # pragma: no cover
    pathspec = None


# -------- Utilities --------

_SIZE_FACTORS = {
    "k": 1024,
    "m": 1024 * 1024,
    "g": 1024 * 1024 * 1024,
}

def parse_size(s: str, default: int) -> int:
    if not s:
        return default
    s = s.strip().lower()
    try:
        if s[-1] in _SIZE_FACTORS:
            return int(float(s[:-1]) * _SIZE_FACTORS[s[-1]])
        return int(s)
    except Exception as e:
        raise ValueError(f"Invalid size value: {s!r}") from e


def is_probably_binary(path: Path, read_bytes: int = 2048) -> bool:
    try:
        with path.open("rb") as f:
            chunk = f.read(read_bytes)
        if b"\x00" in chunk:
            return True
        # Heuristic: proportion of non-text bytes
        text_chars = bytearray({7,8,9,10,12,13,27} | set(range(0x20, 0x100)))
        nontext = chunk.translate(None, text_chars)
        return (len(nontext) / max(1, len(chunk))) > 0.30
    except Exception:
        # If we can't read it, treat as binary to be safe
        return True


def guess_lang_from_suffix(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    mapping = {
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "tsx": "tsx",
        "jsx": "jsx",
        "json": "json",
        "yml": "yaml",
        "yaml": "yaml",
        "toml": "toml",
        "ini": "ini",
        "cfg": "ini",
        "md": "markdown",
        "txt": "",
        "sh": "bash",
        "zsh": "bash",
        "ps1": "powershell",
        "rb": "ruby",
        "go": "go",
        "rs": "rust",
        "java": "java",
        "kt": "kotlin",
        "c": "c",
        "h": "c",
        "cpp": "cpp",
        "hpp": "cpp",
        "cs": "csharp",
        "php": "php",
        "sql": "sql",
        "html": "html",
        "css": "css",
        "vue": "vue",
        "sv": "verilog",
    }
    return mapping.get(ext, "")


# -------- Presets --------

PRESETS = {
    "python": [
        "__pycache__/",
        "*.py[cod]",
        ".mypy_cache/",
        ".pytest_cache/",
        ".tox/",
        ".venv/",
        "venv/",
        "env/",
        "build/",
        "dist/",
        "*.egg-info/",
    ],
    "node": [
        "node_modules/",
        "dist/",
        "build/",
        ".next/",
        ".nuxt/",
        ".cache/",
        "coverage/",
        "*.log",
    ],
}

DEFAULT_GLOBAL_IGNORES = [
    ".git/",
    ".svn/",
    ".hg/",
    ".DS_Store",
    "Thumbs.db",
    ".idea/",
    ".vscode/",
    "*.exe",
    "*.dll",
    "*.bin",
]


@dataclass
class StitchOptions:
    root: Path = Path(".")
    output: Optional[Path] = None
    to_stdout: bool = False
    fmt: str = "md"  # 'md' or 'txt'
    gitignore: Optional[Path] = None
    use_gitignore: bool = True
    preset: Optional[str] = None
    extra_ignores: List[str] = field(default_factory=list)
    include_hidden: bool = False
    max_file_size: int = 1024 * 1024  # 1 MiB
    follow_symlinks: bool = False
    relative_paths: bool = True
    encoding: str = "utf-8"
    quiet: bool = False


class Stitcher:
    def __init__(self, opts: StitchOptions):
        self.o = opts
        self.root = self.o.root.resolve()
        if not self.root.exists() or not self.root.is_dir():
            raise ValueError(f"Root does not exist or is not a directory: {self.root}")

        self._spec = self._build_pathspec()
        self._now = time.strftime("%Y-%m-%d %H:%M:%S")

    def _build_pathspec(self):
        patterns: List[str] = []
        patterns.extend(DEFAULT_GLOBAL_IGNORES)

        if self.o.preset:
            preset = PRESETS.get(self.o.preset.lower())
            if not preset:
                raise ValueError(f"Unknown preset: {self.o.preset}")
            patterns.extend(preset)

        if self.o.use_gitignore:
            gi_path = self.o.gitignore or (self.root / ".gitignore")
            if gi_path.exists():
                try:
                    with open(gi_path, "r", encoding="utf-8", errors="ignore") as f:
                        patterns.extend([line.rstrip("\n") for line in f if line.strip()])
                except Exception:
                    pass

        if self.o.extra_ignores:
            patterns.extend(self.o.extra_ignores)

        if pathspec is None:
            # Minimal fallback with fnmatch (less accurate)
            class _MiniSpec:
                def __init__(self, pats): self.pats = pats
                def match_file(self, relpath):
                    rp = relpath.replace(os.sep, "/")
                    for p in self.pats:
                        if fnmatch.fnmatch(rp, p) or rp.startswith(p.rstrip("*")):
                            return True
                    return False
            return _MiniSpec(patterns)
        else:
            return pathspec.PathSpec.from_lines("gitwildmatch", patterns)

    def _is_ignored(self, rel: str) -> bool:
        return self._spec.match_file(rel)

    def _should_skip(self, path: Path, rel: str) -> bool:
        # Hidden files/dirs
        if not self.o.include_hidden and any(part.startswith(".") for part in Path(rel).parts if part not in (".", "..")):
            # Allow .gitignore if explicitly provided
            return True

        # Ignore patterns
        if self._is_ignored(rel):
            return True

        # File size
        try:
            if path.is_file():
                size = path.stat().st_size
                if size > self.o.max_file_size:
                    return True
        except Exception:
            return True

        # Symlinks
        try:
            if path.is_symlink() and not self.o.follow_symlinks:
                return True
        except Exception:
            return True

        return False

    def _iter_files(self) -> Iterable[Tuple[Path, str]]:
        for dirpath, dirnames, filenames in os.walk(self.root, followlinks=self.o.follow_symlinks):
            # Build relative path
            dir_rel = os.path.relpath(dirpath, self.root)
            if dir_rel == ".":
                dir_rel = ""

            # Filter directories in-place to respect ignores
            keep_dirs = []
            for d in dirnames:
                rel = os.path.join(dir_rel, d) if dir_rel else d
                if self._should_skip(Path(dirpath) / d, rel + "/"):
                    continue
                keep_dirs.append(d)
            dirnames[:] = keep_dirs

            for fn in filenames:
                rel = os.path.join(dir_rel, fn) if dir_rel else fn
                p = Path(dirpath) / fn
                if self._should_skip(p, rel):
                    continue
                yield p, rel.replace(os.sep, "/")

    def _render_tree(self) -> List[str]:
        lines = []
        root_label = self.root.name
        lines.append(f"{root_label}/")
        prefix_stack = [("", self.root)]
        # We'll traverse again to build a sorted tree view with ignores
        def add_dir(path: Path, rel: str, prefix: str):
            try:
                entries = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            except Exception:
                return
            visible = []
            for e in entries:
                r = f"{rel}/{e.name}" if rel else e.name
                test_rel = r + ("/" if e.is_dir() else "")
                if self._should_skip(e, test_rel):
                    continue
                visible.append(e)
            for i, e in enumerate(visible):
                is_last = (i == len(visible) - 1)
                branch = "└── " if is_last else "├── "
                ext_prefix = "    " if is_last else "│   "
                if e.is_dir():
                    lines.append(f"{prefix}{branch}{e.name}/")
                    add_dir(e, f"{rel}/{e.name}" if rel else e.name, prefix + ext_prefix)
                else:
                    lines.append(f"{prefix}{branch}{e.name}")
        add_dir(self.root, "", "")
        return lines

    def _read_text(self, path: Path) -> Optional[str]:
        # Skip device files, fifos, etc.
        try:
            mode = path.stat().st_mode
            if not stat.S_ISREG(mode):
                return None
        except Exception:
            return None

        if is_probably_binary(path):
            return None
        try:
            return path.read_text(encoding=self.o.encoding, errors="replace")
        except Exception:
            return None

    def build(self) -> str:
        files = list(self._iter_files())
        tree_lines = self._render_tree()

        if self.o.fmt == "txt":
            buf = io.StringIO()
            buf.write(f"ContextStitch output\n")
            buf.write(f"Root: {self.root}\n")
            buf.write(f"Generated: {self._now}\n")
            buf.write("="*80 + "\n\n")
            buf.write("FOLDER TREE\n")
            buf.write("-"*80 + "\n")
            for line in tree_lines:
                buf.write(line + "\n")
            buf.write("\n")
            buf.write("FILES\n")
            buf.write("-"*80 + "\n")
            for path, rel in files:
                buf.write(f"--- BEGIN FILE: {rel} ---\n")
                content = self._read_text(path)
                if content is None:
                    buf.write("[Skipped: binary or unreadable]\n")
                else:
                    buf.write(content)
                    if not content.endswith("\n"):
                        buf.write("\n")
                buf.write(f"--- END FILE: {rel} ---\n\n")
            return buf.getvalue()

        # Markdown
        buf = io.StringIO()
        buf.write(f"# ContextStitch Output\n\n")
        buf.write(f"- **Root**: `{self.root}`\n")
        buf.write(f"- **Generated**: {self._now}\n")
        buf.write(f"- **Files included**: {len(files)}\n\n")
        buf.write("## Folder Tree\n\n")
        buf.write("```text\n")
        for line in tree_lines:
            buf.write(line + "\n")
        buf.write("```\n\n")

        buf.write("## Files\n\n")
        for path, rel in files:
            lang = guess_lang_from_suffix(path)
            buf.write(f"### `{rel}`\n\n")
            if lang:
                buf.write(f"```{lang}\n")
            else:
                buf.write("```\n")
            content = self._read_text(path)
            if content is None:
                buf.write("[Skipped: binary or unreadable]\n")
            else:
                buf.write(content)
            if not content or not content.endswith("\n"):
                buf.write("\n")
            buf.write("```\n\n")
        return buf.getvalue()
