"""Static plugin/skill checks; this does not claim installation in a Codex client."""

import json
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main():
    plugin = ROOT / "integrations/codex"
    manifest = json.loads((plugin / "plugin.json").read_text())
    assert manifest["name"] == "learning-brain"
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert manifest["version"] == project["project"]["version"]
    assert manifest["license"] == "GPL-3.0-only"
    assert "hooks" not in manifest
    bootstrap = json.loads((plugin / "hooks/hooks.json").read_text())
    assert set(bootstrap["hooks"]) == {"SessionStart", "SubagentStart", "UserPromptSubmit"}
    for groups in bootstrap["hooks"].values():
        for group in groups:
            for hook in group["hooks"]:
                assert hook["type"] == "command"
                assert hook["timeout"] <= 3
                assert hook["command"] == 'python3 "${PLUGIN_ROOT}/hooks/load_skills.py"'
    assert (plugin / "hooks/load_skills.py").is_file()
    assert (plugin / "scripts/run.py").is_file()
    marketplace = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
    assert marketplace["name"] == "learning-brain-local"
    entry = next(item for item in marketplace["plugins"] if item["name"] == manifest["name"])
    assert (ROOT / entry["source"]["path"]).resolve() == plugin.resolve()
    skills = list((plugin / "skills").glob("*/SKILL.md"))
    assert len(skills) == 2
    for path in skills:
        frontmatter, body = path.read_text()[4:].split("\n---\n", 1)
        metadata = yaml.safe_load(frontmatter)
        assert metadata["name"] == path.parent.name
        assert 20 < len(metadata["description"]) < 1024
        assert body.strip()
    example = json.loads((plugin / "hooks/checkpoints.example.json").read_text())
    assert set(example["hooks"]) == {"Stop", "SessionEnd"}
    for groups in example["hooks"].values():
        for group in groups:
            for hook in group["hooks"]:
                assert hook["timeout"] <= 3
                assert "checkpoint.py" in hook["command"]
    print(
        json.dumps(
            {
                "static_package": "pass",
                "skills": len(skills),
                "hook_discovery": "skill bootstrap only; publication disabled",
                "client_installation": "not tested",
            }
        )
    )


if __name__ == "__main__":
    main()
