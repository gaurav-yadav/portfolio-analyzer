#!/usr/bin/env python3
"""Audit Claude agent reachability and cross-agent references.

Classifies agents into:
- externally_routed: referenced by the OpenClaw trading skill
- internally_referenced: not externally routed, but mentioned by agent prompts
- orphaned: neither externally routed nor referenced by other agents
"""

from __future__ import annotations

import json
import re
from pathlib import Path


BASE = Path(__file__).resolve().parent.parent
AGENTS_DIR = BASE / ".claude" / "agents"
SKILL_PATH = Path("/Users/gauravyadav/.openclaw/workspace/skills/trading-assistant/SKILL.md")

AGENT_NAME_RE = re.compile(r"^name:\s*([a-z0-9-]+)\s*$", re.MULTILINE)
BACKTICK_RE = re.compile(r"`([a-z0-9-]+)`")


def extract_agent_name(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = AGENT_NAME_RE.search(text)
    if not match:
        raise ValueError(f"Missing agent name header in {path}")
    return match.group(1)


def load_agents() -> dict[str, Path]:
    agents: dict[str, Path] = {}
    for path in sorted(AGENTS_DIR.glob("*.md")):
        name = extract_agent_name(path)
        agents[name] = path
    return agents


def extract_skill_routes(skill_text: str, agent_names: set[str]) -> set[str]:
    routes: set[str] = set()

    for agent in agent_names:
        if f"--agent {agent}" in skill_text:
            routes.add(agent)

    return routes


def extract_skill_mentions(skill_text: str, agent_names: set[str]) -> set[str]:
    mentions: set[str] = set()
    for token in BACKTICK_RE.findall(skill_text):
        if token in agent_names:
            mentions.add(token)
    return mentions


def extract_cross_refs(agent_path: Path, agent_names: set[str]) -> set[str]:
    text = agent_path.read_text(encoding="utf-8")
    refs: set[str] = set()

    for token in BACKTICK_RE.findall(text):
        if token in agent_names:
            refs.add(token)

    name = extract_agent_name(agent_path)
    refs.discard(name)
    return refs


def build_report() -> dict:
    agents = load_agents()
    agent_names = set(agents)
    skill_text = SKILL_PATH.read_text(encoding="utf-8") if SKILL_PATH.exists() else ""

    externally_routed = extract_skill_routes(skill_text, agent_names)
    documented_internal = extract_skill_mentions(skill_text, agent_names) - externally_routed

    inbound_refs: dict[str, set[str]] = {name: set() for name in agent_names}
    outbound_refs: dict[str, set[str]] = {}
    for name, path in agents.items():
        refs = extract_cross_refs(path, agent_names)
        outbound_refs[name] = refs
        for ref in refs:
            inbound_refs[ref].add(name)

    internally_referenced = {
        name for name in agent_names
        if name not in externally_routed and inbound_refs[name]
    }

    orphaned = sorted(
        name for name in agent_names
        if name not in externally_routed and name not in documented_internal and not inbound_refs[name]
    )

    return {
        "skill_path": str(SKILL_PATH),
        "agents_dir": str(AGENTS_DIR),
        "counts": {
            "total_agents": len(agent_names),
            "externally_routed": len(externally_routed),
            "internally_referenced_only": len(internally_referenced),
            "documented_internal_only": len(documented_internal),
            "orphaned": len(orphaned),
        },
        "externally_routed": sorted(externally_routed),
        "documented_internal_only": sorted(documented_internal),
        "internally_referenced_only": sorted(internally_referenced),
        "orphaned": orphaned,
        "references": {
            name: {
                "outbound": sorted(outbound_refs[name]),
                "inbound": sorted(inbound_refs[name]),
            }
            for name in sorted(agent_names)
        },
    }


def main() -> None:
    report = build_report()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
