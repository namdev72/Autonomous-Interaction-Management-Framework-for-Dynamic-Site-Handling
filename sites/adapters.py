import re
from datetime import datetime, timezone
from typing import List

from browser.controller import BrowserController
from models.task_models import ProductOffer, SiteRunResult, TaskPlan
from sites.registry import SitePolicy, policy_for


CHALLENGE_MARKERS = (
    "captcha",
    "robot check",
    "verify you are human",
    "sign in to continue",
    "enter your password",
)


def _number(text: str | None) -> float | None:
    if not text:
        return None
    match = re.search(r"[\d,]+(?:\.\d+)?", text)
    return float(match.group(0).replace(",", "")) if match else None


def _rating(text: str | None) -> float | None:
    if not text:
        return None
    match = re.search(r"(\d(?:\.\d)?)\s*out of 5", text, re.IGNORECASE)
    return float(match.group(1)) if match else None


async def _amazon_offers(page, policy: SitePolicy, limit: int = 10) -> List[ProductOffer]:
    cards = page.locator('[data-component-type="s-search-result"]')
    offers = []
    for index in range(min(await cards.count(), limit)):
        card = cards.nth(index)
        title_locator = card.locator("h2").first
        title = (await title_locator.text_content() or "").strip()
        href = await card.locator("h2 a").first.get_attribute("href")
        price = await card.locator(".a-price .a-offscreen").first.text_content()
        rating = await card.locator('[aria-label*="out of 5 stars"]').first.get_attribute("aria-label")
        if title and href:
            offers.append(ProductOffer(
                site=policy.key,
                title=title,
                product_url=f"https://{policy.domains[0]}{href}",
                price=_number(price),
                currency=policy.currency,
                rating=_rating(rating),
                source_timestamp=datetime.now(timezone.utc).isoformat(),
            ))
    return offers


async def _flipkart_offers(page, policy: SitePolicy, limit: int = 10) -> List[ProductOffer]:
    cards = page.locator('div[data-id]')
    offers = []
    for index in range(min(await cards.count(), limit)):
        card = cards.nth(index)
        links = card.locator("a")
        href = await links.first.get_attribute("href") if await links.count() else None
        title = (await links.first.text_content() or "").strip() if href else ""
        text = (await card.text_content() or "").strip()
        if title and href:
            offers.append(ProductOffer(
                site=policy.key,
                title=title,
                product_url=f"https://{policy.domains[0]}{href}",
                price=_number(text),
                currency=policy.currency,
                source_timestamp=datetime.now(timezone.utc).isoformat(),
            ))
    return offers


async def search_site(policy: SitePolicy, task: TaskPlan) -> SiteRunResult:
    controller = BrowserController(headless=True, allowed_hosts=set(policy.domains))
    try:
        if not await controller.open_website(policy.build_search_url(task.subject)):
            return SiteRunResult(site=policy.key, status="failed", warnings=["Initial navigation failed."])
        await controller.wait_for_load()
        body_text = (await controller.page.locator("body").text_content() or "").lower()
        if any(marker in body_text for marker in CHALLENGE_MARKERS):
            return SiteRunResult(site=policy.key, status="blocked", warnings=["Login or human verification is required; no bypass was attempted."])
        if policy.key in {"amazon_in", "amazon_us"}:
            offers = await _amazon_offers(controller.page, policy)
        elif policy.key == "flipkart_in":
            offers = await _flipkart_offers(controller.page, policy)
        else:
            offers = []
        warnings = [] if offers else ["No public product cards were found; the site layout or access state may need review."]
        return SiteRunResult(site=policy.key, status="completed", offers=offers, warnings=warnings)
    except Exception as exc:
        return SiteRunResult(site=policy.key, status="failed", warnings=[str(exc)])
    finally:
        await controller.close_browser()


async def compare_sites(task: TaskPlan) -> List[SiteRunResult]:
    """Run approved public-site adapters sequentially to bound browser load."""
    results = []
    for site in task.candidate_sites:
        results.append(await search_site(policy_for(site), task))
    return results
