"""Static checks that README commands match scripts and generated inputs exist."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def readme_text() -> str:
    return (ROOT / "README.md").read_text(encoding="utf-8")


def bash_blocks(text: str) -> list[str]:
    return re.findall(r"```bash\n(.*?)```", text, flags=re.DOTALL)


def commands(text: str) -> list[str]:
    joined = text.replace("\\\n", " ")
    result = []
    for line in joined.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            result.append(line)
    return result


def script_options(script: Path) -> set[str]:
    tree = ast.parse(script.read_text(encoding="utf-8"))
    options = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument":
            if node.args and isinstance(node.args[0], ast.Constant) and str(node.args[0].value).startswith("--"):
                options.add(node.args[0].value)
    return options


def test_readme_scripts_exist_and_flags_are_valid():
    blocks = bash_blocks(readme_text())
    checked = 0
    for block in blocks:
        for command in commands(block):
            match = re.search(r"(scripts/[\w/]+\.py)", command)
            if not match:
                continue
            script = ROOT / match.group(1)
            assert script.is_file(), f"README references missing script: {match.group(1)}"
            flags = set(re.findall(r"(?<!\w)(--[a-z0-9-]+)", command))
            if flags:
                supported = script_options(script)
                unknown = flags - supported
                assert not unknown, f"{match.group(1)} got unsupported flags {unknown}"
            checked += 1
    assert checked >= 12


def test_readme_generates_inputs_before_use():
    text = readme_text()
    assert text.index("build_video_subset.py") < text.index("extract_frames.py")
    assert text.index("build_inference_annotations.py") < text.index("infer_qwen_vl.py")
    expanded_use = text.index("experiments/ablation/expanded_annotations.json")
    expanded_build = text.index("build_expanded_set.py")
    converter_before_use = text.rfind("build_inference_annotations.py", 0, expanded_use)
    assert expanded_build < converter_before_use < expanded_use


def test_readme_result_paths_exist():
    text = readme_text()
    for match in re.findall(r"results/[A-Za-z0-9_./*-]+", text):
        if "<" in match or "*" in match or match.endswith("/"):
            continue
        assert (ROOT / match).exists(), f"README references missing result path: {match}"


def test_no_absolute_local_paths_in_public_docs():
    documents = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md")),
                 ROOT / "PUBLICATION_AUDIT.md", ROOT / "REORGANIZATION_REPORT.md"]
    pattern = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]|(?<![A-Za-z0-9])/(?:d|mnt|home)/[A-Za-z0-9_.-]+/")
    offenders = []
    for document in documents:
        for line_number, line in enumerate(document.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{document.relative_to(ROOT)}:{line_number}: {line.strip()[:80]}")
    assert not offenders, "absolute local paths found:\n" + "\n".join(offenders)


def test_documentation_links_resolve():
    text = readme_text()
    for target in re.findall(r"\]\(([^)#]+)\)", text):
        if target.startswith("http"):
            continue
        assert (ROOT / target).exists(), f"broken README link: {target}"
