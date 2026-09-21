from typing import Optional, Union
import re
from loguru import logger
from models.task_models import TaskPlan
from models.strategy_models import DirectURLStrategy, RegistryStrategy, LLMStrategy
from router.website_registry import WebsiteRegistry
from router.query_normalizer import QueryNormalizer
from router.url_generator import URLGenerator

class TaskRouter:
    def __init__(self):
        self.registry = WebsiteRegistry()
        self.normalizer = QueryNormalizer()
        self.generator = URLGenerator(self.registry)

    def route_task(self, user_query: str, plan: TaskPlan) -> Union[DirectURLStrategy, RegistryStrategy, LLMStrategy]:
        logger.info("[Agent] Understanding user request...")
        
        if plan.needs_clarification:
            return LLMStrategy(query=user_query)
            
        from sites.registry import classify_sites
        actual_sites = classify_sites(user_query)
        if not actual_sites:
            logger.info("[Agent] No explicitly approved website detected in query. Falling back to LLM.")
            return LLMStrategy(query=user_query)
            
        if not plan.preferred_sites:
            logger.info("[Agent] No specific website detected in plan. Falling back to LLM.")
            return LLMStrategy(query=user_query)
            
        primary_site = plan.preferred_sites[0].lower()
        website_key = "amazon" if "amazon" in primary_site else ("flipkart" if "flipkart" in primary_site else primary_site)
        
        region = "in"
        if "us" in primary_site:
            region = "us"
            
        logger.info(f"[Agent] Website detected: {website_key.title()} (Region: {region})")
        
        search_query = self.normalizer.normalize_search_query(plan.subject, website_key)
        
        if plan.task_type in ["search", "compare"] and search_query:
            logger.info(f"[Agent] {plan.task_type.title()} intent detected for query: '{search_query}'")
            direct_url = self.generator.generate_direct_url(
                website_key=website_key,
                intent=plan.task_type,
                search_query=search_query,
                region=region
            )
            
            if direct_url:
                logger.info("[Agent] Direct URL strategy available")
                logger.info(f"[Agent] Generated search URL: {direct_url}")
                return DirectURLStrategy(
                    url=direct_url,
                    website=website_key,
                    source_locked=True
                )
                
        config = self.registry.get_website_config(website_key)
        if config:
            domain = self.registry.get_domain(website_key, region)
            if domain:
                logger.info(f"[Agent] URL generation unavailable, using Website Registry for {domain}")
                return RegistryStrategy(
                    config=config,
                    domain=domain,
                    website=website_key,
                    source_locked=True
                )
                
        logger.info("[Agent] Registry strategy unavailable. Falling back to LLM strategy.")
        return LLMStrategy(query=user_query)

