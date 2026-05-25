"""
Common utilities for Layer5 agents.
"""
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("layer5")


def load_json(file_path: str | Path) -> dict:
    """Load a JSON file and return as dict."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(data: dict, file_path: str | Path) -> None:
    """Save dict as JSON file."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_upstream_files(output_dir: Path, form_name: str, agent_name: str) -> list[dict]:
    """
    Load generated files from a previous agent's output.
    Used by downstream agents to read upstream output WITHOUT importing the agent.
    """
    form_dir = output_dir / form_name
    if not form_dir.exists():
        logger.warning(f"No upstream output found for {form_name}")
        return []
    
    files = []
    for f in form_dir.rglob("*.cs"):
        files.append({
            "path": str(f.relative_to(form_dir)),
            "content": f.read_text(encoding="utf-8"),
        })
    for f in form_dir.rglob("*.xaml"):
        files.append({
            "path": str(f.relative_to(form_dir)),
            "content": f.read_text(encoding="utf-8"),
        })
    for f in form_dir.rglob("*.json"):
        files.append({
            "path": str(f.relative_to(form_dir)),
            "content": f.read_text(encoding="utf-8"),
        })
    return files


def read_prompt(agent_name: str, prompt_name: str) -> str:
    """Read a prompt file from agents/{agent_name}/prompts/{prompt_name}."""
    prompt_path = Path(__file__).parent.parent / "agents" / agent_name / "prompts" / prompt_name
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")
