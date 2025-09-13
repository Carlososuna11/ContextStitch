from pathlib import Path
from contextstitch.stitcher import Stitcher, StitchOptions

def test_run_tmp(tmp_path: Path):
    # create small sample repo
    (tmp_path / "a.py").write_text("print('hello')\n", encoding="utf-8")
    (tmp_path / "binary.bin").write_bytes(b"\x00\x01\x02")
    opts = StitchOptions(root=tmp_path, fmt="md", use_gitignore=False)
    st = Stitcher(opts)
    output = st.build()
    assert "a.py" in output
    assert "binary or unreadable" in output
