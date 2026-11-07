"""Static plugin/skill checks; this does not claim installation in a Codex client."""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main():
    plugin = ROOT / "integrations/codex"
    manifest = json.loads((plugin / "plugin.json").read_text())
    assert manifest["name"] == "learning-brain"
    assert manifest["version"] == "0.1.0"
    assert manifest["license"] == "GPL-3.0-only"
    assert "hooks" not in manifest
    assert not (plugin / "hooks/hooks.json").exists(), "Hooks must remain opt-in"
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
                "hook_discovery": "disabled",
                "client_installation": "not tested",
            }
        )
    )


if __name__ == "__main__":
    main()
