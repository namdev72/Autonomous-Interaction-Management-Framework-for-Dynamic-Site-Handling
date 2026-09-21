import uuid
import json
from loguru import logger
from models.goal_models import GoalContract, GoalRequirement
from llm.llm_client import LLMClient

class GoalCompiler:
    """Converts natural language user queries into structured GoalContracts."""
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    async def compile(self, user_query: str) -> GoalContract:
        logger.info("Compiling user query into GoalContract...")
        system_prompt = """
        You are the Goal Compiler for a web automation agent.
        Convert the user's natural language query into a structured Goal Contract.
        The Goal Contract contains a list of generic predicates (requirements) that must be true for the task to be considered COMPLETE.
        
        Requirement types: content, page, navigation, state, interaction, extraction, download, comparison, form, custom.
        
        Return a JSON object matching this structure exactly:
        {
            "intent": "open_product_variant",
            "source": {"website": "amazon"},
            "requirements": [
                {
                    "id": "product_page",
                    "type": "page",
                    "description": "Must be on a product details page",
                    "required": true
                },
                {
                    "id": "product_identity",
                    "type": "content",
                    "description": "Product must match iPhone 16",
                    "required": true
                }
            ]
        }
        Make sure you define specific, observable requirements based on the user's explicit query.
        """
        user_prompt = f"User Query: {user_query}"
        
        response = await self.llm_client.generate_json(system_prompt, user_prompt)
        if not response:
            logger.warning("Failed to compile goal, using fallback.")
            return self._fallback_goal(user_query)
            
        try:
            requirements = []
            for req in response.get("requirements", []):
                requirements.append(GoalRequirement(
                    id=req.get("id", str(uuid.uuid4())[:8]),
                    type=req.get("type", "custom"),
                    description=req.get("description", ""),
                    required=req.get("required", True)
                ))
                
            return GoalContract(
                task_id=str(uuid.uuid4()),
                intent=response.get("intent", "unknown"),
                source=response.get("source", {}),
                requirements=requirements
            )
        except Exception as e:
            logger.error(f"Error parsing GoalContract: {e}")
            return self._fallback_goal(user_query)
            
    def _fallback_goal(self, user_query: str) -> GoalContract:
        return GoalContract(
            task_id=str(uuid.uuid4()),
            intent="unknown",
            requirements=[
                GoalRequirement(
                    id="fallback",
                    type="custom",
                    description=f"Fulfill the query: {user_query}"
                )
            ]
        )
