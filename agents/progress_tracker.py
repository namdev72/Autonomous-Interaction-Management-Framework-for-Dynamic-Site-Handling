from loguru import logger
import hashlib
from models.goal_models import ObservedState

class ProgressTracker:
    def __init__(self):
        self.history = []
        self.MAX_NO_PROGRESS = 3
        
    def fingerprint(self, state: ObservedState) -> str:
        """Identity of the page state; equal fingerprints mean nothing changed."""
        return self._hash_state(state)

    def _hash_state(self, state: ObservedState) -> str:
        selected_strs = [str(x) for x in state.selected_states]
        # Scroll position and input values are included because the page text
        # does not change when the agent scrolls or types.
        form_strs = [f"{f.get('field')}={f.get('value')}" for f in state.forms]
        s = (
            f"{state.url}|{state.title}|{'|'.join(selected_strs)}|{'|'.join(state.visible_text[:10])}"
            f"|scroll={state.scroll_y}|{'|'.join(form_strs)}"
        )
        return hashlib.md5(s.encode()).hexdigest()
        
    def is_stuck(self, state: ObservedState) -> bool:
        current_hash = self._hash_state(state)
        self.history.append(current_hash)
        
        # Check if the last N hashes are identical
        if len(self.history) >= self.MAX_NO_PROGRESS:
            recent = self.history[-self.MAX_NO_PROGRESS:]
            if len(set(recent)) == 1:
                logger.warning("Agent appears stuck (no meaningful state change).")
                return True
        return False
