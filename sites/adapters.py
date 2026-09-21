import re
from datetime import datetime, timezone
from typing import List
from urllib.parse import urljoin

from loguru import logger

from browser.controller import BrowserController
from models.task_models import UNAVAILABLE_STATUSES, ProductOffer, SiteRunResult, TaskPlan
from sites.registry import SitePolicy, policy_for


CHALLENGE_MARKERS = (
    "captcha",
    "robot check",
    "verify you are human",
    "sign in to continue",
    "enter your password",
)
NON_PRODUCT_TERMS = ("case", "cover", "charger", "adapter", "screen protector", "stand", "cable")


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


def _relevant_title(title: str, subject: str) -> bool:
    tokens = [token for token in re.findall(r"[a-z0-9]+", subject.lower()) if len(token) > 1]
    if not tokens:
        return True
    matches = sum(token in title.lower() for token in tokens)
    return matches >= min(2, len(tokens))


def _is_candidate(title: str, subject: str) -> bool:
    """Drop accessories and unrelated results, so they cannot win on price."""
    return not any(term in title.lower() for term in NON_PRODUCT_TERMS) and _relevant_title(title, subject)


async def _amazon_offers(page, policy: SitePolicy, subject: str, limit: int = 10) -> List[ProductOffer]:
    cards = page.locator('[data-component-type="s-search-result"]')
    offers = []
    for index in range(min(await cards.count(), limit)):
        card = cards.nth(index)
        title_links = card.locator('a[href*="/dp/"], a[href*="/gp/product/"]')
        if await title_links.count() == 0:
            continue
        title_locator = card.locator("h2").first
        title = (await title_locator.text_content() or "").strip()
        if not _is_candidate(title, subject):
            continue
        href = await title_links.first.get_attribute("href", timeout=3000)
        price_locator = card.locator(".a-price .a-offscreen")
        price = await price_locator.first.text_content(timeout=3000) if await price_locator.count() else None
        rating_locator = card.locator('[aria-label*="out of 5 stars"]')
        rating = await rating_locator.first.get_attribute("aria-label", timeout=3000) if await rating_locator.count() else None
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


# Flipkart's class names are generated and change between deploys, so cards are
# read by structure. Both result layouts (list for phones, grid for
# accessories) share it: the selling price is the first element whose whole
# text is a rupee amount and that is not struck through (the struck one is the
# MRP), and the rating is the badge whose whole text is a 1-5 score. Short
# text lines are returned too, for status labels such as "Coming Soon".
FLIPKART_CARDS_JS = r"""
(limit) => [...document.querySelectorAll('div[data-id]')].slice(0, limit).map(card => {
  const text = el => (el.innerText || '').trim();
  const struck = el => getComputedStyle(el).textDecorationLine.includes('line-through');
  const elements = [...card.querySelectorAll('*')];
  const leaves = elements.filter(el => el.children.length === 0);
  const link = card.querySelector('a[href*="/p/"]');
  const price = leaves.find(el => /^₹[\d,]+(\.\d+)?$/.test(text(el)) && !struck(el));
  const rating = elements.find(el => /^[1-5](\.\d)?$/.test(text(el)));
  return {
    href: link ? link.getAttribute('href') : null,
    title: card.querySelector('a[title]')?.getAttribute('title') || card.querySelector('img[alt]')?.getAttribute('alt') || '',
    price: price ? text(price) : null,
    rating: rating ? text(rating) : null,
    lines: text(card).split('\n').map(line => line.trim()).filter(line => line && line.length <= 40),
  };
})
"""


def _status_label(lines: List[str]) -> str | None:
    """The card's not-purchasable label, if it shows one."""
    return next((line for line in lines if line.lower() in UNAVAILABLE_STATUSES), None)


async def _flipkart_offers(page, policy: SitePolicy, subject: str, limit: int = 10) -> List[ProductOffer]:
    try:
        await page.wait_for_selector("div[data-id]", timeout=5000)
    except Exception:
        return []
    offers = []
    for card in await page.evaluate(FLIPKART_CARDS_JS, limit):
        title = card["title"].strip()
        if not (title and card["href"]) or not _is_candidate(title, subject):
            continue
        offers.append(ProductOffer(
            site=policy.key,
            title=title,
            product_url=urljoin(f"https://{policy.domains[0]}/", card["href"]),
            price=_number(card["price"]),
            currency=policy.currency,
            rating=float(card["rating"]) if card["rating"] else None,
            availability=_status_label(card.get("lines", [])),
            source_timestamp=datetime.now(timezone.utc).isoformat(),
        ))
    return offers


async def search_site(policy: SitePolicy, task: TaskPlan) -> SiteRunResult:
    controller = BrowserController(headless=True, allowed_hosts=set(policy.domains))
    try:
        if not await controller.open_website(policy.build_search_url(task.subject)):
            return SiteRunResult(site=policy.key, status="failed", warnings=["Initial navigation failed."])
        controller.page.set_default_timeout(5000)
        await controller.wait_for_load()
        body_text = (await controller.page.locator("body").text_content() or "").lower()
        if any(marker in body_text for marker in CHALLENGE_MARKERS):
            return SiteRunResult(site=policy.key, status="blocked", warnings=["Login or human verification is required; no bypass was attempted."])
        if policy.key in {"amazon_in", "amazon_us"}:
            offers = await _amazon_offers(controller.page, policy, task.subject)
        elif policy.key == "flipkart_in":
            offers = await _flipkart_offers(controller.page, policy, task.subject)
        else:
            offers = []
        warnings = [] if offers else ["No public product cards were found; the site layout or access state may need review."]
        return SiteRunResult(site=policy.key, status="completed", offers=offers, warnings=warnings)
    except Exception as exc:
        return SiteRunResult(site=policy.key, status="failed", warnings=[str(exc)])
    finally:
        # A crashed browser also fails to close; raising here would replace the
        # result above and abort the remaining sites.
        try:
            await controller.close_browser()
        except Exception as exc:
            logger.warning(f"Failed to close browser for {policy.key}: {exc}")


async def compare_sites(task: TaskPlan) -> List[SiteRunResult]:
    """Run approved public-site adapters sequentially to bound browser load."""
    results = []
    for site in task.candidate_sites:
        results.append(await search_site(policy_for(site), task))
    return results
