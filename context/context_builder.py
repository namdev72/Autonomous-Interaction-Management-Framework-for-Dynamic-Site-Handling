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
            # Build a descriptive string for each element
            desc_parts = [f"{el.get('playwright_index')}. [{el.get('tag').upper()}]"]
            
            if el.get("text"):
                desc_parts.append(f"Text: '{el.get('text')}'")
            if el.get("placeholder"):
                desc_parts.append(f"Placeholder: '{el.get('placeholder')}'")
            if el.get("aria_label"):
                desc_parts.append(f"Aria-label: '{el.get('aria_label')}'")
            if el.get("type"):
                desc_parts.append(f"Type: '{el.get('type')}'")
                
            context_lines.append(" ".join(desc_parts))
            
        context_text = "\n".join(context_lines)
        logger.debug(f"Generated Context:\n{context_text}")
        return context_text
