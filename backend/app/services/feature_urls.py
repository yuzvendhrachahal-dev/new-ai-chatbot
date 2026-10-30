"""
AstroVed Feature URLs Service.
Backed by the comprehensive URL Catalogue service (url_catalogue.py).
Authoritative source of truth for AstroVed feature redirects from data/all_urls.txt.
"""

from typing import Set
from app.services.url_catalogue import url_catalogue_service


def get_verified_urls() -> Set[str]:
    """Loads and caches the set of all verified URLs from all_urls.txt."""
    return url_catalogue_service.get_all_verified_urls()


FEATURE_URLS_IN_SOURCE = {
    "todays_horoscope": "https://www.astroved.com/horoscope/",
    "compatibility_matching": "https://www.astroved.com/astropedia/en/freetools/horoscope-matching",
    "compatibility_zodiac": "https://www.astroved.com/zodiac-signs/compatibility",
    "sade_sati": "https://www.astroved.com/astropedia/en/freetools/sade-sati",
    "numerology": "https://www.astroved.com/astropedia/en/freetools/numerology",
    "nakshatras": "https://www.astroved.com/astropedia/en/nakshatra",
    "virtual_pooja": "https://www.astroved.com/astropedia/en/virtual-pooja"
}


def get_feature_url(feature_key: str) -> str:
    """Returns verified URL for a feature key if available."""
    if feature_key in FEATURE_URLS_IN_SOURCE:
        return FEATURE_URLS_IN_SOURCE[feature_key]

    match = url_catalogue_service.search(feature_key)
    if match.entry:
        return match.entry.url

    return ""


MISSING_URLS_REPORT = {
    "free_birth_chart": {
        "status_in_all_urls_txt": "MISSING",
        "description": "Free birth chart generation tool is not indexed in all_urls.txt.",
        "fallback_strategy": "Offer human support / live astrologer consultation via AstroVed Speaks."
    },
    "panchang": {
        "status_in_all_urls_txt": "MISSING",
        "description": "Daily panchang calendar tool is not indexed in all_urls.txt.",
        "fallback_strategy": "Direct to customer support or live astrologer."
    },
    "muhurta": {
        "status_in_all_urls_txt": "MISSING",
        "description": "Muhurta calculation tool is not indexed in all_urls.txt.",
        "fallback_strategy": "Direct to AstroVed Speaks consultation."
    }
}
