"""Build an allowlisted source archive and verify it before atomic replacement."""
from pathlib import Path
import hashlib
import json
import os
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]


def main():
    report = json.loads((ROOT / "reports/learning.json").read_text(encoding="utf-8"))
    capture = json.loads((ROOT / "docs/screenshots/capture.json").read_text(encoding="utf-8"))
    # Reject evidence from stale source, fixtures or modified screenshots.
    hashes = {**report["source_sha256"], **capture["source_sha256"],
              **{row["file"]: row["sha256"] for row in report["splits"].values()},
              **{f"docs/screenshots/{name}": digest for name, digest in capture["screenshot_sha256"].items()}}
    for name, expected in hashes.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, f"Stale evidence: {name}"
    files = [ROOT / name for name in ["app.py", "README.md", "PORTFOLIO.md", "requirements.txt", "constraints-verified.txt",
                                     ".gitignore", ".gitattributes", ".github/workflows/ci.yml", "docs/PROJECT_GUIDE.md",
                                     ".streamlit/config.toml", "reports/learning.json", "reports/learning.md",
                                     "docs/screenshots/README.md", "docs/screenshots/capture.json"]]
    files.extend(ROOT / "data" / f"demo_{name}.csv" for name in ("seed", "feedback", "validation", "eval"))
    files.extend(ROOT / "docs" / "screenshots" / f"{profile}-{name}.png"
                 for profile in ("desktop", "mobile")
                 for name in ("inbox", "review", "candidate", "prediction-changes", "evaluation", "matrices", "versions"))
    for folder, pattern in [("inboxlearn", "*.py"), ("tests", "*.py"), ("scripts", "*.py"), ("assets", "*.css"), ("data", "*.md")]:
        files.extend(sorted((ROOT / folder).glob(pattern)))
    archive_path = ROOT / "InboxLearn.zip"
    temporary_path = ROOT / "InboxLearn.zip.tmp"
    with ZipFile(temporary_path, "w", compression=ZIP_DEFLATED) as archive:
        for file in files:
            archive.write(file, file.relative_to(ROOT).as_posix())
    with ZipFile(temporary_path) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(set(archive.namelist())) == len(files)
        for file in files:
            name = file.relative_to(ROOT).as_posix()
            assert archive.read(name) == file.read_bytes(), name
            assert not any(part in {".venv", "runtime", "__pycache__", ".pytest_cache"} for part in Path(name).parts)
    os.replace(temporary_path, archive_path)
    print(f"Verified {len(files)} source, evidence and curated screenshot files; no environments, databases, caches or model binaries.")
    print(f"{archive_path} ({archive_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
