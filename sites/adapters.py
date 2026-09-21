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
CHALLENGE_JS = """
(markers) => {
  const text = (document.body?.textContent || '').toLowerCase();
  return markers.some(marker => text.includes(marker));
}
"""
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


def _tokens(text: str) -> List[str]:
    # Decimals stay whole, so "16.63 cm" is one token and never reads as "16".
    return re.findall(r"[a-z0-9]+(?:\.\d+)?", text.lower())


def _relevant_title(title: str, subject: str) -> bool:
    tokens = [token for token in _tokens(subject) if len(token) > 1]
    if not tokens:
        return True
    title_lower = title.lower()
    title_tokens = set(_tokens(title))

    def found(token: str) -> bool:
        # A token with a digit is a model identifier ("16", "s6") and must
        # match a whole title token: "16" is not in "16e" or "16.63". Words
        # match loosely, so "shoe" still finds "shoes".
        if any(char.isdigit() for char in token):
            return token in title_tokens
        return token in title_lower

    return sum(found(token) for token in tokens) >= min(2, len(tokens))


def _join_title(headings: List[str]) -> str:
    """Amazon splits a card's title into a brand heading and a product heading."""
    parts = [heading.strip() for heading in headings if heading.strip()]
    # Drop a heading the next one already starts with ("Apple", "Apple iPhone").
    kept = [part for i, part in enumerate(parts)
            if not any(later.lower().startswith(part.lower()) for later in parts[i + 1:])]
    return " ".join(kept)


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
        # The first heading is often just the brand ("Apple"), so a title read
        # from it alone fails the relevance check for every such card.
        title = _join_title(await card.locator("h2").all_text_contents())
        if not _is_candidate(title, subject):
            continue
        href = await title_links.first.get_attribute("href", timeout=3000)
        price_locator = card.locator(".a-price .a-offscreen")
        price = await price_locator.first.text_content(timeout=3000) if await price_locator.count() else None
        rating_locator = card.locator('[aria-label*="out of 5 stars"]')
        rating = await rating_locator.first.get_attribute("aria-label", timeout=3000) if await rating_locator.count() else None
        # The visible count is rounded ("2.7K"); the link's label is exact.
        count_locator = card.locator('a[href*="customerReviews"][aria-label]')
        rating_count = await count_locator.first.get_attribute("aria-label", timeout=3000) if await count_locator.count() else None
        if title and href:
            offers.append(ProductOffer(
                site=policy.key,
                title=title,
                product_url=f"https://{policy.domains[0]}{href}",
                price=_number(price),
                currency=policy.currency,
                rating=_rating(rating),
                review_count=_rating_count(rating_count),
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


def _rating_count(text: str | None) -> int | None:
    """Ratings behind a score, from Amazon's "2,701 ratings" label."""
    match = re.fullmatch(r"\s*([\d,]+)\s+ratings?\s*", text or "", re.IGNORECASE)
    return int(match.group(1).replace(",", "")) if match else None


def _flipkart_rating_count(lines: List[str], rating: str | None) -> int | None:
    """
    Ratings behind a Flipkart score. List cards (phones) show
    "1,98,941 Ratings & 8,603 Reviews" and grid cards (accessories) show
    "(9,003)", but the card text runs the score into both: "4.61,98,941
    Ratings", "4.2(9,003)". The score is known, so it is removed first;
    guessing where it ends fails for a whole-number score ("512 Ratings").
    """
    for line in lines:
        if rating and line.startswith(rating):
            line = line[len(rating):]
        match = re.match(r"\s*([\d,]+)\s+Ratings\b", line, re.IGNORECASE) or re.fullmatch(r"\s*\(([\d,]+)\)", line)
        if match:
            return int(match.group(1).replace(",", ""))
    return None


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
            review_count=_flipkart_rating_count(card.get("lines", []), card["rating"]),
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
        # Scanned inside the page: copying a heavy page's whole text out of the
        # browser just to search it has run the driver out of memory.
        if await controller.page.evaluate(CHALLENGE_JS, list(CHALLENGE_MARKERS)):
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
