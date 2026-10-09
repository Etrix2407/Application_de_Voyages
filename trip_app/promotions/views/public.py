"""Page publique « Nos offres du moment » : promotions automatiques en cours, jamais les codes."""

from django.shortcuts import render

from orders.services.promotions import public_offers


def offers(request):
    return render(request, "promotions/offers.html", {"offers": public_offers()})
