from models.task_models import SiteRunResult, TaskPlan


def _by_price(offers):
    return sorted(offers, key=lambda offer: offer.price or float("inf"))


def compose_comparison_answer(task: TaskPlan, results: list[SiteRunResult]) -> dict:
    priced = [offer for result in results for offer in result.offers if offer.price is not None]
    # Offers that cannot be bought now (e.g. "Coming Soon") are never ranked,
    # so they cannot be reported as the lowest price.
    offers = [offer for offer in priced if offer.is_available]
    unavailable = _by_price(offer for offer in priced if not offer.is_available)
    minimum_rating = float(task.constraints.get("minimum_rating", "0"))
    maximum_price = float(task.constraints.get("maximum_price", "inf"))
    filtered = [
        offer for offer in offers
        if (offer.rating or 0) >= minimum_rating and offer.price <= maximum_price
    ]
    ranked = _by_price(filtered or offers)
    warnings = [warning for result in results for warning in result.warnings]
    if not priced:
        answer = "I could not find public offers matching the request."
    elif not offers:
        answer = f"I found {len(unavailable)} offer(s), but none can be bought right now."
    elif not filtered:
        # Offers exist but every one failed a constraint. Say which, rather
        # than presenting the unfiltered list as matches.
        unmet = []
        if minimum_rating > 0:
            unmet.append(f"a rating of at least {minimum_rating:g}/5")
        if maximum_price != float("inf"):
            currency = f"{task.currency} " if task.currency else ""
            unmet.append(f"the budget of {currency}{maximum_price:,.2f}")
        answer = f"I found {len(offers)} offer(s), but none met {' and '.join(unmet)}."
    else:
        lines = [f"Found {len(ranked)} public offer(s) for {task.subject}:"]
        for index, offer in enumerate(ranked[:10], 1):
            count = f" ({offer.review_count:,} ratings)" if offer.review_count is not None else ""
            rating = f", rating {offer.rating}/5{count}" if offer.rating is not None else ""
            lines.append(f"{index}. {offer.site}: {offer.title} - {offer.currency} {offer.price:,.2f}{rating}")
        lines.append(f"Lowest matching price: {ranked[0].currency} {ranked[0].price:,.2f} on {ranked[0].site}.")
        answer = "\n".join(lines)
    if unavailable and offers:
        labels = ", ".join(sorted({offer.availability for offer in unavailable}))
        answer += f"\nLeft out {len(unavailable)} offer(s) that cannot be bought right now ({labels})."
    return {
        "answer": answer,
        # Unavailable offers are still shown, after the ranked ones and
        # labelled, rather than silently dropped.
        "offers": [offer.model_dump() for offer in ranked + unavailable],
        "sites": [result.model_dump() for result in results],
        "warnings": warnings,
    }
