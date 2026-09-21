from typing import Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

class StrategyBase(BaseModel):
    strategy_type: Literal["direct_url", "registry", "llm"]
    website: str = "unknown"

class DirectURLStrategy(StrategyBase):
    strategy_type: Literal["direct_url"] = "direct_url"
    url: str
    source_locked: bool = True

class RegistryStrategy(StrategyBase):
    strategy_type: Literal["registry"] = "registry"
    config: Dict[str, Any] = Field(default_factory=dict)
    source_locked: bool = True
    domain: str

class LLMStrategy(StrategyBase):
    strategy_type: Literal["llm"] = "llm"
    query: str

