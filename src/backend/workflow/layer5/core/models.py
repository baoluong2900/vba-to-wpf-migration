"""
Shared models & contracts for Layer5 agents.
Mỗi agent implement BaseAgent — giao tiếp qua AgentInput/AgentOutput.

Pipeline flow (không cache):
    MongoDB → Agent Repo → Agent Service → Agent Logic → Agent UI → WPF source
    Mỗi bước đọc output của bước trước từ agents/{name}/outputs/ trực tiếp.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


@dataclass
class GeneratedFile:
    """Represents a single generated output file."""
    path: str           # relative path: "Domain/Entities/IdPassEntity.cs"
    content: str        # file content
    generator: str      # "jinja2" | "llm" | "deterministic"
    agent: str          # "repo" | "service" | "logic" | "ui" | "graphview" | "test"


@dataclass
class AgentInput:
    """Standard input for all agents."""
    form_name: str
    bd_json: dict = field(default_factory=dict)
    dd_json: dict = field(default_factory=dict)
    mongodb_data: dict = field(default_factory=dict)   # forms, macros, modules, tables
    upstream_files: list[GeneratedFile] = field(default_factory=list)  # output from previous agents
    output_dir: Path = field(default_factory=lambda: Path("output"))
    model_override: Optional[object] = None            # ModelConfig override from CLI --model
    # Service agent: event filter for unified input
    service_filter_mode: str = "any_repo_signal"
    # When True, write agents/service/inputs/{form}_service_input.json after building
    persist_service_input_json: bool = False
    # Service agent: "tool" = deterministic; "llm" = LLM
    service_codegen_mode: str = "tool"
    # Whether to include verbose step comments in the generated service
    service_include_comments: bool = False
    # Logic agent: event class filter ("ui" | "service" | "all")
    logic_event_class: str = "all"


@dataclass
class AgentOutput:
    """Standard output from all agents."""
    agent: str
    form_name: str
    files: list[GeneratedFile] = field(default_factory=list)
    status: str = "success"   # "success" | "error"
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class BaseAgent(ABC):
    """
    Base class for all Layer 5 agents.

    Subclasses implement:
      - name  → agent identifier string
      - run() → reads MongoDB + upstream outputs, produces GeneratedFile list

    NO caching — every run reads fresh from MongoDB and the previous agent's
    outputs/ folder. Pipeline order is enforced by the orchestrator.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent name: 'repo' | 'service' | 'logic' | 'ui' | 'graphview' | 'test'"""
        ...

    @abstractmethod
    async def run(self, input: AgentInput) -> AgentOutput:
        """Execute the agent and return generated files."""
        ...

    def load_prompt(self, prompt_name: str) -> str:
        """Load a prompt .md file from this agent's prompts/ folder."""
        from core.config import TARGET_LANGUAGE
        prompt_dir = Path(__file__).parent.parent / "agents" / self.name / "prompts"
        prompt_file = prompt_dir / prompt_name
        if not prompt_file.exists():
            raise FileNotFoundError(f"Prompt not found: {prompt_file}")
        content = prompt_file.read_text(encoding="utf-8")
        return content.replace("{TARGET_LANGUAGE}", TARGET_LANGUAGE)

    def save_output(self, output: AgentOutput, output_dir: Path) -> None:
        """Save generated files to output directory."""
        for gf in output.files:
            file_path = output_dir / output.form_name / gf.path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(gf.content, encoding="utf-8")
