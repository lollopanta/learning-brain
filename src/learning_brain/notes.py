from __future__ import annotations

import re

import yaml

from .errors import BrainError

CATEGORIES = {"concepts", "entities", "skills", "references", "synthesis", "journal"}


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str) or key in result:
            raise BrainError("Frontmatter keys must be unique strings")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


class VaultDumper(yaml.SafeDumper):
    def increase_indent(self, flow=False, indentless=False):
        # obsidian-wiki's field scanner requires indented block lists.
        return super().increase_indent(flow, indentless=False)


class Folded(str):
    pass


VaultDumper.add_representer(
    Folded,
    lambda dumper, value: dumper.represent_scalar("tag:yaml.org,2002:str", str(value), style=">"),
)


def parse_note(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        raise BrainError("Existing note needs YAML frontmatter before it can be updated")
    parts = text.split("\n---\n", 1)
    if len(parts) != 2:
        raise BrainError("Unterminated frontmatter")
    try:
        header = yaml.load(parts[0][4:], Loader=UniqueLoader)
    except yaml.YAMLError as exc:
        raise BrainError("Invalid YAML frontmatter") from exc
    if not isinstance(header, dict):
        raise BrainError("Frontmatter must be a mapping")
    return header, parts[1].strip()


def dump_note(header: dict, body: str) -> str:
    header = dict(header)
    for key in ("title", "summary"):
        if isinstance(header.get(key), str):
            header[key] = Folded(header[key])
    return (
        "---\n"
        + yaml.dump(header, Dumper=VaultDumper, allow_unicode=True, sort_keys=False, width=10_000)
        + "---\n\n"
        + body.strip()
        + "\n"
    )


def page_path(path: str) -> str:
    """Return category; disallow service files and ambiguous path syntax."""
    if not isinstance(path, str) or not re.fullmatch(r"[A-Za-z0-9_/-]+\.md", path):
        raise BrainError("Note path must use portable ASCII names and end in .md")
    parts = path.split("/")
    if parts[0] == "projects":
        if len(parts) != 4 or parts[2] not in CATEGORIES:
            raise BrainError("Project targets use projects/<name>/<category>/<slug>.md")
        return parts[2]
    if len(parts) != 2 or parts[0] not in CATEGORIES:
        raise BrainError("Target must be a category note, not a service or configuration file")
    return parts[0]
