"""
Stable identifiers for a page and for what its viewport currently shows.

Two values, one normalizer, because there are two questions:

- page_key: which page is this? Derived from the URL alone, so scrolling
  cannot fragment a single page into many keys. Used as the vector-store
  document id, and later as the graph node id.
- view_signature: what is the viewport showing right now? Derived from the
  URL plus the visible element descriptors, so it changes when the page
  changes under an action. Used to verify that a step actually did something.

Descriptors deliberately exclude playwright_index and frame- tokens. The
extractor recounts them on every extraction and only returns in-viewport
elements, so they renumber on scroll and are not stable identity.
"""

import hashlib
import re
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Query parameters that carry session or tracking state rather than page
# identity. Captured URLs in this project routinely arrive with crid/sprefix/
# ref attached to what is otherwise the same page. Denylist rather than
# allowlist, so meaningful params (a search term such as ?k=iphone) survive.
TRACKING_PARAMS = {
    "_encoding", "crid", "creative", "creativeasin", "linkcode", "psc", "qid",
    "ref", "ref_", "sprefix", "sr", "tag", "th",
    "fbclid", "gclid", "igshid", "mc_eid", "msclkid", "si", "spm",
    "utm_campaign", "utm_content", "utm_id", "utm_medium", "utm_source", "utm_term",
}

# Element fields that survive a re-extraction. id and className are excluded
# alongside the index tokens: both are frequently framework-generated
# (react-select-3-input, CSS-in-JS class hashes) and change between builds.
DESCRIPTOR_FIELDS = ("tag", "role", "type", "aria_label", "placeholder")

# Visible text is the least stable field kept -- prices, rating counts and
# timestamps all move. Truncated to limit how much of that noise lands in the
# signature. Expect to tune this against real captures.
MAX_TEXT = 80

_WHITESPACE = re.compile(r"\s+")


def _clean(value: Any) -> str:
    """Collapse whitespace so re-extracted text compares equal."""
    if not value:
        return ""
    return _WHITESPACE.sub(" ", str(value)).strip()


def _href_path(href: str) -> str:
    """Path only. Query strings on links carry session state, not identity."""
    try:
        return urlsplit(href).path or "/"
    except ValueError:
        return _clean(href)


def normalize_url(url: str) -> str:
    """
    Reduce a URL to page identity.

    Lowercases scheme and host, drops "www." and the fragment, strips tracking
    parameters, sorts what remains, and removes a trailing slash.
    """
    if not url:
        return ""

    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url.strip()

    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]

    netloc = host
    default_port = (scheme == "http" and parts.port == 80) or (scheme == "https" and parts.port == 443)
    if parts.port and not default_port:
        netloc = f"{host}:{parts.port}"

    path = parts.path or "/"
    if len(path) > 1:
        path = path.rstrip("/") or "/"

    kept = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS
    ]
    kept.sort()

    return urlunsplit((scheme, netloc, path, urlencode(kept), ""))


def page_key(url: str) -> str:
    """Identity of the page itself. Stable across scrolling and tracking junk."""
    digest = hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()
    return f"page_{digest[:32]}"


def element_descriptor(element: Dict[str, Any]) -> str:
    """One element reduced to the attributes that survive re-extraction."""
    parts = []
    for field in DESCRIPTOR_FIELDS:
        value = _clean(element.get(field))
        if value:
            parts.append(f"{field}={value}")

    text = _clean(element.get("text"))
    if text:
        parts.append(f"text={text[:MAX_TEXT]}")

    href = element.get("href")
    if href:
        parts.append(f"href={_href_path(href)}")

    # Same text in two different iframes is not the same element.
    frame_url = element.get("frame_url")
    if frame_url:
        parts.append(f"frame={normalize_url(frame_url)}")

    return "|".join(parts)


def descriptor_for_target(target: Optional[str], elements: Iterable[Dict[str, Any]]) -> Optional[str]:
    """
    Reduce the element an action targeted to a descriptor that outlives it.

    A stored action cannot reference pw-id-3: indices are recounted on every
    extraction and depend on the viewport, so the same element is a different
    index tomorrow. The descriptor is what a later run matches against to find
    the element again.

    Returns None when the action had no target (a page-level scroll) or the
    target is no longer in the extracted set.
    """
    if not target or not elements:
        return None

    for element in elements:
        if element.get("playwright_index") == target:
            return element_descriptor(element) or None
    return None


def target_for_descriptor(descriptor: Optional[str], elements: Iterable[Dict[str, Any]]) -> Optional[str]:
    """
    Find today's pw-id for an element remembered by descriptor.

    The inverse of descriptor_for_target, and what makes a recalled action
    executable: a memory says "the Search submit worked here", this turns that
    back into the index the current extraction assigned it.

    Returns None when the remembered element is not in the current viewport,
    which is a normal outcome, not an error -- it may need scrolling to.
    """
    if not descriptor or not elements:
        return None

    for element in elements:
        if element_descriptor(element) == descriptor:
            return element.get("playwright_index")
    return None


def view_signature(url: str, elements: Iterable[Dict[str, Any]]) -> str:
    """
    What the viewport is showing, as one comparable value.

    Sorted, so DOM reordering alone does not read as a change. Scroll-sensitive
    by construction: the extractor returns only in-viewport elements, so
    scrolling changes this value. That is what makes a scroll verifiable.
    """
    descriptors: List[str] = sorted(
        d for d in (element_descriptor(e) for e in (elements or [])) if d
    )
    payload = normalize_url(url) + "\n" + "\n".join(descriptors)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"view_{digest[:32]}"
