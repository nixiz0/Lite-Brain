from typing import List

def parse_ids_csv(raw: str) -> List[int]:
    """
    Parses a comma-separated list of integers (e.g. "1,2,3") into a list of ints.
    Ignores empty values and surrounding whitespace.
    """
    if not raw:
        return []  # No input → return empty list
    
    # Split by comma, strip whitespace, and convert valid segments to int.
    return [int(x) for x in raw.split(",") if x.strip()]
