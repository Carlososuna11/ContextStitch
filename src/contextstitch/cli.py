from __future__ import annotations

import argparse
import sys
from pathlib import Path
from .stitcher import Stitcher, StitchOptions, parse_size

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="contextstitch",
        description="Concatenate your repository into a single Markdown/TXT context file (folder tree + file contents).",
    )
    p.add_argument("--root", type=Path, default=Path("."), help="Root directory to stitch (default: .)")
    p.add_argument("--output", type=Path, help="Output file path (default: auto-named)")
    p.add_argument("--stdout", action="store_true", help="Write to stdout instead of a file")
    p.add_argument("--format", dest="fmt", choices=["md", "txt"], default="md", help="Output format (default: md)")
    p.add_argument("--gitignore", type=Path, help="Path to a .gitignore to respect")
    p.add_argument("--no-gitignore", action="store_true", help="Do not respect .gitignore even if present")
    p.add_argument("--preset", choices=["python", "node"], help="Language/stack preset for ignores")
    p.add_argument("--ignore", dest="extra_ignores", action="append", default=[], help="Extra ignore pattern (repeatable)")
    p.add_argument("--include-hidden", action="store_true", help="Include dotfiles/directories")
    p.add_argument("--max-file-size", default="1m", help="Skip files larger than SIZE (e.g., 500k, 2m), default 1m")
    p.add_argument("--follow-symlinks", action="store_true", help="Follow symlinks")
    p.add_argument("--absolute-paths", action="store_true", help="Use absolute paths in output (default: relative)")
    p.add_argument("--encoding", default="utf-8", help="Default text encoding (default: utf-8)")
    p.add_argument("--quiet", action="store_true", help="Reduce log output")
    p.add_argument("--version", action="store_true", help="Print version and exit")
    return p

def main(argv=None) -> int:
    from . import __version__
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    opts = StitchOptions(
        root=args.root,
        output=args.output,
        to_stdout=args.stdout,
        fmt=args.fmt,
        gitignore=args.gitignore,
        use_gitignore=not args.no_gitignore,
        preset=args.preset,
        extra_ignores=args.extra_ignores,
        include_hidden=args.include_hidden,
        max_file_size=parse_size(args.max_file_size, 1024*1024),
        follow_symlinks=args.follow_symlinks,
        relative_paths=not args.absolute_paths,
        encoding=args.encoding,
        quiet=args.quiet,
    )

    try:
        st = Stitcher(opts)
        content = st.build()
        if opts.to_stdout:
            sys.stdout.write(content)
        else:
            out = opts.output
            if out is None:
                suffix = ".md" if opts.fmt == "md" else ".txt"
                out = Path.cwd() / (f"contextstitch-{int(__import__('time').time())}{suffix}")
            out.write_text(content, encoding="utf-8")
            if not opts.quiet:
                print(f"Wrote {out}")
        return 0
    except Exception as e:
        if not getattr(args, "quiet", False):
            print(f"error: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
