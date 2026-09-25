"""
Deterministic alphabetical sorter and group arrangement manager.
Orders groups according to customizable settings, and within each group,
sorts authorities letter-by-letter with strict tie-breaking.
"""
import re
from typing import List, Dict, Optional, Tuple
from .models import AuthorityItem, AuthorityCategory, GroupConfig

# Default group definitions in order
DEFAULT_GROUP_ORDER: List[str] = [
    AuthorityCategory.SINGAPORE_CASES.value,
    AuthorityCategory.SINGAPORE_STATUTES.value,
    AuthorityCategory.REGULATIONS.value,
    AuthorityCategory.FOREIGN_CASES.value,
    AuthorityCategory.FOREIGN_STATUTES.value,
    AuthorityCategory.SECONDARY_SOURCES.value,
    AuthorityCategory.MISCELLANEOUS.value,
]


def normalize_for_sort(text: str) -> str:
    """
    Normalizes a title for strict alphabetical sorting:
    - Strips leading quotes, hyphens, brackets
    - Converts to lowercase (casefold)
    - Normalizes internal whitespace
    """
    t = text.strip()
    # Strip leading non-alphanumeric characters (quotes, apostrophes, brackets, dots)
    t = re.sub(r'^[^a-zA-Z0-9]+', '', t)
    # Convert to lowercase
    t = t.casefold()
    # Collapse whitespace
    t = re.sub(r'\s+', ' ', t)
    return t


def alphabetical_sort_key(item: AuthorityItem) -> str:
    """
    Returns the deterministic sort key for an authority.
    Scans the alphabet of the first letter, then second, then third, etc.
    """
    # Primary sorting is by the title
    key = normalize_for_sort(item.title)
    if not key and item.raw_citation:
        key = normalize_for_sort(item.raw_citation)
    return key


def get_default_group_configs() -> List[GroupConfig]:
    """Generates the default GroupConfig objects."""
    return [
        GroupConfig(
            id=cat,
            title=cat,
            order=idx + 1,
            visible=True,
            merged_into=None
        )
        for idx, cat in enumerate(DEFAULT_GROUP_ORDER)
    ]


def sort_and_group_authorities(
    authorities: List[AuthorityItem],
    custom_order: Optional[List[str]] = None,
    merged_groups: Optional[Dict[str, str]] = None
) -> Dict[str, List[AuthorityItem]]:
    """
    Groups authorities and sorts them within each group alphabetically.
    Returns an ordered dictionary mapping {group_title: [sorted_authorities]}.
    """
    group_order = custom_order if custom_order else DEFAULT_GROUP_ORDER
    merges = merged_groups or {}

    # Initialize buckets for all groups in order. A combined group takes the place of the first of its
    # members, so combining Foreign Cases and Foreign Statutes keeps them where Foreign Cases stood.
    grouped: Dict[str, List[AuthorityItem]] = {}
    for g in group_order:
        grouped.setdefault(merges.get(g, g), [])
    # Add any merged target groups whose members aren't in the order at all
    for target in merges.values():
        grouped.setdefault(target, [])

    # Distribute each included authority into its appropriate group
    for auth in authorities:
        if not auth.included:
            continue
            
        cat_name = auth.category.value
        # Check if this category is merged into another
        target_group = merges.get(cat_name, cat_name)
        
        if target_group not in grouped:
            grouped[target_group] = []
        grouped[target_group].append(auth)

    # Sort each group alphabetically
    result: Dict[str, List[AuthorityItem]] = {}
    for group_name in grouped:
        items = grouped[group_name]
        if not items:
            continue
        # Deterministic sorting letter by letter
        sorted_items = sorted(items, key=alphabetical_sort_key)
        result[group_name] = sorted_items

    return result
