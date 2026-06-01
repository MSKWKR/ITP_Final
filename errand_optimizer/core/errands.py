"""Errand category definitions.

Maps user-facing errand categories to the Nominatim search query terms used to
find candidate locations, and stores an estimated time spent inside each kind of
stop (the "dwell" time). Both are used by the optimizer when scoring routes.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Errand:
    """A single errand category the user can choose."""

    key: str          # stable identifier used in forms / URLs
    label: str        # human-readable name shown in the UI
    query: str        # term passed to Nominatim's free-form search
    visit_minutes: int  # estimated time spent at this stop


# Ordered so the UI can render a sensible checkbox list.
ERRANDS: dict[str, Errand] = {
    e.key: e
    for e in [
        Errand("atm", "ATM", "atm", 3),
        Errand("pharmacy", "Pharmacy", "pharmacy", 5),
        Errand("convenience", "Convenience store", "convenience store", 5),
        Errand("supermarket", "Supermarket", "supermarket", 15),
        Errand("post_office", "Post office", "post office", 8),
        Errand("cafe", "Café", "cafe", 12),
        Errand("bookstore", "Bookstore", "bookstore", 10),
        Errand("bakery", "Bakery", "bakery", 5),
        Errand("hardware", "Hardware store", "hardware store", 10),
    ]
}


def get_errand(key: str) -> Errand:
    """Look up an errand by key, raising a clear error for unknown keys."""
    try:
        return ERRANDS[key]
    except KeyError:
        raise ValueError(f"Unknown errand category: {key!r}")


def all_errands() -> list[Errand]:
    """Return every errand in display order."""
    return list(ERRANDS.values())
