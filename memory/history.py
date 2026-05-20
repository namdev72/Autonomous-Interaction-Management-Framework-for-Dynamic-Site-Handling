from typing import List, Dict, Any
from models.action_models import AgentAction
from loguru import logger

class MemoryState:
    def __init__(self):
        self.actions_history: List[AgentAction] = []
        self.visited_urls: List[str] = []
        self.extracted_data: Dict[str, Any] = {}
        
    def add_action(self, action: AgentAction):
        self.actions_history.append(action)
        
    def add_url(self, url: str):
        if not self.visited_urls or self.visited_urls[-1] != url:
            self.visited_urls.append(url)
            
    def store_extracted_data(self, key: str, value: Any):
        self.extracted_data[key] = value
        logger.info(f"Stored in memory: {key} = {value}")
        
    def get_context_string(self) -> str:
        """Returns a string representation of recent history for the LLM prompt."""
        recent_actions = self.actions_history[-5:] # Last 5 actions
        history_strs = [f"- {a.action} on {a.target} (Reason: {a.reasoning})" for a in recent_actions]
        
        context = "Recent Actions Taken:\n" + ("\n".join(history_strs) if history_strs else "None")
        if self.extracted_data:
            context += f"\n\nExtracted Data So Far:\n{self.extracted_data}"
        return context
