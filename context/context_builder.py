from typing import List, Dict, Any
from loguru import logger

class ContextBuilder:
    def build_memory_recall(
        self,
        actions: List[Dict[str, Any]],
        routes: List[Dict[str, Any]],
    ) -> str:
        """
        Render what memory recalled about this page into prompt text.

        Actions come first and carry their live target where the remembered
        element is on screen right now, so the model can act on one directly.
        Where it is not on screen the memory is still worth stating -- it tells
        the model the element exists and is worth scrolling to.
        """
        lines = []

        if actions:
            lines.append("Actions previously verified on this page:")
            for a in actions:
                bits = [f"- {a.get('action')}"]
                live = a.get("live_target")
                if live:
                    bits.append(f"on {live}")
                elif a.get("target_descriptor"):
                    bits.append(f"on an element matching [{a.get('target_descriptor')}] (not currently visible)")
                if a.get("value"):
                    bits.append(f"with value '{a.get('value')}'")
                if a.get("evidence"):
                    bits.append(f"({a.get('evidence')})")
                lines.append(" ".join(bits))

        if routes:
            if lines:
                lines.append("")
            lines.append("Routes known to lead away from this page:")
            for r in routes:
                seen = r.get("times_seen", 1)
                descriptor = r.get("target_descriptor") or ""
                where = f" via [{descriptor}]" if descriptor else ""
                lines.append(f"- {r.get('action')}{where} -> {r.get('to_page')} (taken {seen}x)")

        if not lines:
            return ""

        return "Recalled Memory:\n" + "\n".join(lines)

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
            if el.get("frame_url"):
                desc += f" frame:'{el.get('frame_url')}'"
                
            context_lines.append(desc)
            
            # Truncate to prevent exceeding free-tier LLM token limits (e.g. Groq's 8000 TPM limit)
            # 15,000 characters is roughly 3,500 tokens
            if sum(len(line) for line in context_lines) > 15000:
                context_lines.append("... [DOM TRUNCATED DUE TO MAX TOKEN LIMITS] ...")
                break
            
        context_text = "\n".join(context_lines)
        logger.debug(f"Generated Context:\n{context_text}")
        return context_text
