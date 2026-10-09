"""Page de recherche du catalogue (le filtrage est dans services/search.py)."""

from django.shortcuts import render

from catalog.forms import SearchForm
from catalog.services.search import search
from reviews.services.ratings import attach_ratings


def search_page(request):
    form = SearchForm(request.GET or None)
    results = None
    if form.is_valid() and not form.criteria().is_empty():
        results = search(form.criteria())
        results.destinations = attach_ratings(results.destinations)
    return render(request, "catalog/search.html", {"form": form, "results": results})
