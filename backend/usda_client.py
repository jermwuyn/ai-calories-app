
import os
import json

from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


BASE_URL = "https://api.nal.usda.gov/fdc/v1"


def search_foods(query: str, page_size: int = 10):

    api_key = os.getenv("FDC_API_KEY", "").strip()

    if not api_key:
        raise ValueError("FDC_API_KEY is not configured")

    payload = {
        "query": query,
        "dataType": ["Foundation", "SR Legacy"],
        "pageSize": page_size,
    }

    request = Request(
        f"{BASE_URL}/foods/search",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    except HTTPError as error:
        raise RuntimeError(
            f"USDA API returned HTTP {error.code}"
        ) from error

    except URLError as error:
        raise RuntimeError(
            "Unable to connect to USDA API"
        ) from error


def get_food_details(fdc_id: int):
    from urllib.request import Request, urlopen

    api_key = os.getenv("FDC_API_KEY", "").strip()
    if not api_key:
        raise ValueError("FDC_API_KEY is not configured")

    request = Request(
        f"{BASE_URL}/food/{fdc_id}",
        headers={
            "X-Api-Key": api_key,
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=30) as response:
        return json.load(response)


if __name__ == "__main__":
    food = get_food_details(168930)

    print("FDC ID:", food.get("fdcId"))
    print("Name:", food.get("description"))
    print("Type:", food.get("dataType"))
    print("Nutrient entries:", len(food.get("foodNutrients", [])))
    print("-" * 65)

    keywords = (
        "energy",
        "protein",
        "carbohydrate",
        "total lipid",
    )

    for item in food.get("foodNutrients", []):
        nutrient = item.get("nutrient") or {}
        name = nutrient.get("name", "")

        if any(word in name.lower() for word in keywords):
            print(
                f"{name}: "
                f"{item.get('amount', 'N/A')} "
                f"{nutrient.get('unitName', '')}"
            )
