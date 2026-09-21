from models.task_models import SiteRunResult, TaskPlan


def compose_comparison_answer(task: TaskPlan, results: list[SiteRunResult]) -> dict:
    offers = [offer for result in results for offer in result.offers if offer.price is not None]
    minimum_rating = float(task.constraints.get("minimum_rating", "0"))
    maximum_price = float(task.constraints.get("maximum_price", "inf"))
    filtered = [
        offer for offer in offers
        if (offer.rating or 0) >= minimum_rating and offer.price <= maximum_price
    ]
    ranked = sorted(filtered or offers, key=lambda offer: offer.price or float("inf"))
    warnings = [warning for result in results for warning in result.warnings]
    if not ranked:
        answer = "I could not find public offers matching the request."
    elif not filtered and maximum_price != float("inf"):
        answer = f"I found offers, but none were within the budget of {task.currency} {maximum_price:,.2f}."
        ranked = sorted(offers, key=lambda offer: offer.price or float("inf"))
    else:
        lines = [f"Found {len(ranked)} public offer(s) for {task.subject}:"]
        for index, offer in enumerate(ranked[:10], 1):
            rating = f", rating {offer.rating}/5" if offer.rating is not None else ""
            lines.append(f"{index}. {offer.site}: {offer.title} - {offer.currency} {offer.price:,.2f}{rating}")
        lines.append(f"Lowest matching price: {ranked[0].currency} {ranked[0].price:,.2f} on {ranked[0].site}.")
        answer = "\n".join(lines)
    return {
        "answer": answer,
        "offers": [offer.model_dump() for offer in ranked],
        "sites": [result.model_dump() for result in results],
        "warnings": warnings,
    }
