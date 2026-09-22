from loguru import logger
from llm.llm_client import LLMClient
from models.goal_models import GoalContract, ObservedState, VerificationResult

class GoalVerifier:
    """Evaluates the GoalContract against the ObservedState to determine completion."""
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    async def verify(self, contract: GoalContract, state: ObservedState) -> VerificationResult:
        logger.info("Evaluating goal completion against observed state...")
        system_prompt = """
        You are the Goal Verifier. Evaluate if the Goal Contract requirements are satisfied by the Current State.
        
        Return ONLY a JSON object:
        {
            "status": "ACHIEVED" | "NOT_ACHIEVED" | "UNKNOWN",
            "confidence": 0.0 to 1.0,
            "evidence": {"found_text": "...", "selected_state": "..."},
            "answer_parts": ["...", "..."],
            "missing": "..." | null
        }
        
        ACHIEVED: All required predicates in the contract are met.
        NOT_ACHIEVED: The page definitively proves the goal is NOT met (e.g. wrong page, required text missing).
        UNKNOWN: Insufficient evidence to decide.

        answer_parts: if the goal asks for information (a price, a time, a name, the cheapest option),
        the values that answer it, all from the same result, each copied exactly from one line of
        the Current State text. A request to find or search flights asks for information: the
        first flight listed (the cheapest, if asked for). Include the trip type and date when the page shows them, e.g.
        ["Example Air", "9:05 PM", "11:20 PM", "Nonstop", "$212", "One way", "Mar 3"].
        For a product, the result must be the product the goal names, model number included: a
        different model ("MX Master 4" when the goal names "MX Master 3S") or a result marked
        Sponsored does not answer it, even when listed first. Give the product's title as one part
        and each value as its own part, e.g. ["Example Mouse 3S Wireless", "4.6 out of 5 stars",
        "17,208 ratings"].
        For a question asking how many, each item counted as its own part and nothing else (no
        title, no heading), since the answer shown is the number of parts, e.g. for storage
        variants ["128 GB", "256 GB", "512 GB"].
        Otherwise [].

        missing: when not ACHIEVED, the one thing that still has to happen on this page, as an
        instruction naming the control to use if there is one, e.g. "Choose 'Size: M' in the size
        picker; no size is chosen." Otherwise null.
        """
        # Compact JSON: indentation adds tokens on every call for no benefit to the model.
        user_prompt = f"Goal Contract:\n{contract.model_dump_json()}\n\nCurrent State Evidence:\n{state.model_dump_json()}"

        response = await self.llm_client.generate_json(system_prompt, user_prompt)
        if not response:
            return VerificationResult(status="UNKNOWN", confidence=0.0)
            
        status = response.get("status", "UNKNOWN")
        confidence = float(response.get("confidence", 0.5))
        evidence = response.get("evidence", {})
        parts = response.get("answer_parts") or []
        answer_parts = [part.strip() for part in parts if isinstance(part, str) and part.strip()] if isinstance(parts, list) else []
        missing = response.get("missing")
        missing = missing.strip() if isinstance(missing, str) and missing.strip() and status != "ACHIEVED" else None

        logger.info(f"Verification Result: {status} (Confidence: {confidence})" + (f" Missing: {missing}" if missing else ""))
        return VerificationResult(status=status, confidence=confidence, evidence=evidence,
                                  answer_parts=answer_parts, missing=missing)
