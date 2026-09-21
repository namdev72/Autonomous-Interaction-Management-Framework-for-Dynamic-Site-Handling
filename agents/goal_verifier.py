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
            "answer_parts": ["...", "..."]
        }
        
        ACHIEVED: All required predicates in the contract are met.
        NOT_ACHIEVED: The page definitively proves the goal is NOT met (e.g. wrong page, required text missing).
        UNKNOWN: Insufficient evidence to decide.

        answer_parts: if the goal asks for information (a price, a time, a name, the cheapest option),
        the values that answer it, all from the same result, each copied exactly from one line of
        the Current State text. Include the trip type and date when the page shows them, e.g.
        ["Example Air", "9:05 PM", "11:20 PM", "Nonstop", "$212", "One way", "Mar 3"].
        Otherwise [].
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
        
        logger.info(f"Verification Result: {status} (Confidence: {confidence})")
        return VerificationResult(status=status, confidence=confidence, evidence=evidence, answer_parts=answer_parts)
