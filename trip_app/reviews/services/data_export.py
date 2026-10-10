"""RGPD (portabilité) : avis d'un client, prêts à être exportés.

Le client y retrouve ce qu'il voit dans « Mes avis », réponse de l'agence comprise.
"""

from reviews.models import Review


def reviews_data(client) -> list[dict]:
    reviews = Review.objects.filter(order__client=client).select_related("order", "response")
    return [_review_data(review) for review in reviews]


def _review_data(review: Review) -> dict:
    response = getattr(review, "response", None)
    return {
        "order_id": review.order_id,
        "destination": review.order.destination_name,
        "rating": review.rating,
        "title": review.title,
        "comment": review.comment,
        "anonymous": review.anonymous,
        "signature": review.signature,
        "status": review.get_status_display(),
        "refusal_reason": review.get_refusal_reason_display(),
        "refusal_details": review.refusal_details,
        "created_at": review.created_at,
        "published_at": review.published_at,
        "agency_response": None
        if response is None
        else {
            "author_first_name": response.author_first_name,
            "text": response.text,
            "created_at": response.created_at,
            "updated_at": response.updated_at,
        },
    }
