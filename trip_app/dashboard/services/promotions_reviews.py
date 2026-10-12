"""Section « Promotions et avis » du tableau de pilotage : réunit les deux résumés, calculés à part."""

from dashboard.services.periods import Period
from dashboard.services.promotion_figures import promotion_figures
from dashboard.services.review_figures import review_figures


def promotions_reviews(period: Period) -> dict:
    return {"promotions": promotion_figures(period), "reviews": review_figures(period)}
