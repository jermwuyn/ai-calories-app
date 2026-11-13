
from backend.usda_client import search_foods

# Candidate searches for Bun bo Hue.

QUERIES = {
    "Pork hock": "Pork, hock",
    "Pork shoulder": "Pork, shoulder, cooked",
    "Lemongrass": "Lemongrass, raw",
    "Onion": "Onions, raw",
    "Garlic": "Garlic, raw",
    "Chili": "Peppers, hot chili, red, raw",
    "Beef broth": "Soup, stock, beef",
    "Coriander": "Coriander (cilantro) leaves, raw",
    "Shrimp paste": "Shrimp paste",
}



def main():
    print("=== USDA INGREDIENT DISCOVERY ===")
    print("Data type: SR Legacy")
    print("Mode: SEARCH ONLY - NO DATABASE WRITES")

    for label, query in QUERIES.items():
        print(f"\n{'=' * 60}")
        print("Ingredient:", label)
        print("Query:", query)

        response = search_foods(
            query=query,
            page_size=20,
        )

        foods = (
            response.get("foods", [])
            if isinstance(response, dict)
            else response
        )

        # Existing importer currently supports SR Legacy.
        candidates = [
            food for food in foods
            if food.get("dataType") == "SR Legacy"
        ]

        if not candidates:
            print("No SR Legacy candidates found.")
            print("Manual review required.")
            continue

        for food in candidates[:5]:
            print(
                f"FDC ID: {food.get('fdcId')} | "
                f"{food.get('description')}"
            )

    print("\nUSDA DISCOVERY COMPLETED")


if __name__ == "__main__":
    main()
