from typing import List, Dict, Any
from loguru import logger

class ContextBuilder:
    def build_context(self, current_url: str, elements: List[Dict[str, Any]]) -> str:
        """
        Converts the raw extracted DOM elements into a concise text representation
        optimized for the LLM context window.
        """
        logger.info("Building context from DOM elements...")
        
        context_lines = [f"Current URL: {current_url}", "Available Interactive Elements:"]
        
        for el in elements:
            desc = f"{el.get('playwright_index')} [{el.get('tag').upper()}]"
            
            if el.get("text"):
                desc += f" '{el.get('text')}'"
            if el.get("placeholder"):
                desc += f" pl:'{el.get('placeholder')}'"
            if el.get("aria_label"):
                desc += f" aria:'{el.get('aria_label')}'"
            if el.get("type"):
                desc += f" type:{el.get('type')}"
                
            context_lines.append(desc)
            
            # Truncate to prevent exceeding free-tier LLM token limits (e.g. Groq's 8000 TPM limit)
            # 15,000 characters is roughly 3,500 tokens
            if sum(len(line) for line in context_lines) > 15000:
                context_lines.append("... [DOM TRUNCATED DUE TO MAX TOKEN LIMITS] ...")
                break
            
        context_text = "\n".join(context_lines)
        logger.debug(f"Generated Context:\n{context_text}")
        return context_text
