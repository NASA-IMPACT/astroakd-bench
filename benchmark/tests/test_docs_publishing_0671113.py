"""Offline checks for current-only GitHub Pages + GitHub Wiki publishing."""
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _run(*args):
    return subprocess.run([sys.executable, *map(str, args)], check=True, capture_output=True, text=True)


def test_workflow_deploys_html_and_wiki_from_main():
    flow = ROOT / ".github/workflows/publish-docs.yml"
    obj = yaml.load(flow.read_text(), Loader=yaml.BaseLoader)
    assert obj["on"]["push"]["branches"] == ["main"]
    assert "docs/**" in obj["on"]["push"]["paths"]
    assert "examples/**" in obj["on"]["push"]["paths"]
    assert "README.md" in obj["on"]["push"]["paths"]
    assert "workflow_dispatch" in obj["on"]
    assert obj["permissions"] == {"contents": "write", "pages": "write", "id-token": "write"}
    steps = obj["jobs"]["publish"]["steps"]
    run_commands = "\n".join(step.get("run", "") for step in steps)
    assert "-b html -n -W --keep-going" in run_commands
    assert "astroakd-html/index.html" in run_commands
    assert "publish_gh_pages.sh" in run_commands
    assert "publish_wiki.sh" in run_commands
    assert any(step.get("uses") == "actions/upload-pages-artifact@v3" for step in steps)
    assert any(step.get("uses") == "actions/deploy-pages@v4" for step in steps)


def test_wiki_export_rewrites_internal_links_and_preserves_code(tmp_path):
    output = tmp_path / "wiki"
    _run(ROOT / "scripts/export_wiki.py", "--output", output)
    home = (output / "Home.md").read_text()
    guide = (output / "AstroAKD-Getting-Started.md").read_text()
    assert "[Getting started](AstroAKD-Getting-Started)" in home
    assert "{toctree}" not in home
    assert "[ADS and MCP connectivity](AstroAKD-ADS-and-MCP)" in guide
    assert "```bash" in guide
    assert (output / "_Sidebar.md").exists()
    assert (output / "AstroAKD-README.md").exists()
    assert (output / "AstroAKD-Changelog.md").exists()
    assert len(list(output.glob("*.md"))) == 12
    assert "[published `astroakd_100_v2` example](AstroAKD-Example-Results)" in home
    example = (output / "AstroAKD-Example-Results.md").read_text()
    assert f"raw.githubusercontent.com/{os.environ.get('GITHUB_REPOSITORY', 'danehkar/astroakd-bench')}/main/docs/_static/examples/match_rate.png" in example
    assert "![](_static/" not in home


def test_wiki_sync_preserves_unmanaged_and_prunes_removed_managed(tmp_path):
    source = tmp_path / "generated"
    source.mkdir()
    (source / "Home.md").write_text("# New home\n")
    (source / "_Sidebar.md").write_text("[Home](Home)\n")
    (source / "AstroAKD-Guide.md").write_text("# Guide\n")
    target = tmp_path / "wiki"
    target.mkdir()
    (target / ".git").mkdir()
    (target / "Personal-Notes.md").write_text("# Please retain\n")
    (target / "Old-Managed.md").write_text("# Retired\n")
    (target / ".astroakd-bench-managed-pages.json").write_text(json.dumps({"managed_pages": ["Old-Managed.md"]}))
    _run(ROOT / "scripts/sync_wiki.py", "--source", source, "--target", target)
    assert (target / "Personal-Notes.md").read_text() == "# Please retain\n"
    assert not (target / "Old-Managed.md").exists()
    assert (target / "AstroAKD-Guide.md").read_text() == "# Guide\n"
    manifest = json.loads((target / ".astroakd-bench-managed-pages.json").read_text())
    assert manifest["managed_pages"] == ["AstroAKD-Guide.md", "Home.md", "_Sidebar.md"]


def test_shell_scripts_parse_and_site_root_guard():
    for name in ("publish_gh_pages.sh", "publish_wiki.sh"):
        subprocess.run(["bash", "-n", str(ROOT / "scripts" / name)], check=True)
    assert (ROOT / "docs/index.md").is_file()
    assert (ROOT / "docs/conf.py").is_file()
    assert (ROOT / "docs/requirements.txt").is_file()
    assert (ROOT / "docs/sphinx/Makefile").is_file()


def test_gh_pages_mirror_create_skip_and_same_size_update(tmp_path):
    """A same-byte-count HTML edit must be published, not skipped by timestamp heuristics."""
    import os

    remote = tmp_path / "remote.git"
    main = tmp_path / "main"
    site = tmp_path / "site"
    main.mkdir()
    site.mkdir()
    index = site / "index.html"
    index.write_text("<html>v1</html>\n")
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    subprocess.run(["git", "init", "-b", "main", "-q"], cwd=main, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=main, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=main, check=True)
    (main / "README.md").write_text("Baseline\n")
    subprocess.run(["git", "add", "README.md"], cwd=main, check=True)
    subprocess.run(["git", "commit", "-qm", "Baseline"], cwd=main, check=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=main, check=True)
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=main, check=True)

    def publish(number: int) -> str:
        env = dict(os.environ, GITHUB_REPOSITORY="test/astroakd", GITHUB_SHA="smoke")
        subprocess.run(
            ["bash", str(ROOT / "scripts/publish_gh_pages.sh"), str(site), str(tmp_path / f"worktree-{number}")],
            cwd=main, env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return subprocess.check_output(["git", "--git-dir", str(remote), "rev-parse", "gh-pages"], text=True).strip()

    a = publish(1)
    assert b"v1" in subprocess.check_output(["git", "--git-dir", str(remote), "show", "gh-pages:index.html"])
    assert a == publish(2)  # unchanged source
    index.write_text("<html>v2</html>\n")  # identical length and potentially timestamp
    b = publish(3)
    assert b != a
    assert b"v2" in subprocess.check_output(["git", "--git-dir", str(remote), "show", "gh-pages:index.html"])
