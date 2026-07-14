# AGENTS.md

This file gives AI coding agents a quick, reliable map of the Smart Grocery project. Read it before making changes.

## Project Summary

Smart Grocery is a Django web app for grocery shopping and store management. It supports customer and shop-owner flows:

- Customers can browse products, search/filter the catalog, add to cart, checkout, view orders, download invoices, track budgets, earn/redeem reward points, maintain grocery lists, request unavailable items, and scan grocery list images.
- Shop owners can manage inventory, create offers, view dashboard metrics, inspect orders, handle unavailable-item requests, and review monthly reports.
- The app also includes Gemini grocery-image parsing and a TF-IDF recommendation helper.

## Main Stack

- Python
- Django
- SQLite for local development
- HTML templates with app CSS
- ReportLab for PDF invoices
- Google Gen AI SDK for Gemini 3.1 Flash-Lite image parsing
- Pillow for image handling
- Pandas, NumPy, scikit-learn, and RapidFuzz for recommendation logic

## Important Paths

```text
manage.py                         Django command entrypoint
requirements.txt                  Python dependencies
.env.example                      Safe template for local env values
products.csv                      Product import data
smart_grocery/settings.py         Django settings and env loading
smart_grocery/urls.py             Project-level routes
grocery_app/models.py             Core data models
grocery_app/views.py              Main request handlers
grocery_app/urls.py               App routes
grocery_app/templates/            Django templates
grocery_app/static/css/style.css  App styling
grocery_app/management/commands/  Product/import inventory commands
grocery_app/ml_models/            Recommendation code and training data
grocery_app/services/             External service integrations
```

## Data Model Overview

Core models live in `grocery_app/models.py`:

- `Store`: grocery store owned by a user
- `Category`: product category
- `Product`: shared product catalog
- `InventoryItem`: per-store product stock, price, and expiry date
- `UserProfile`: role and user preferences
- `ShoppingList` and `ShoppingListItem`: customer grocery lists
- `Offer`: store product discounts
- `ItemRequest`: customer request for unavailable products
- `Cart` and `CartItem`: active customer cart
- `CustomerOrder`: completed customer order snapshot
- `MonthlyBudget`: customer budget for a month/year

## Setup Commands

Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create local env config:

```bash
cp .env.example .env
```

Run migrations:

```bash
python manage.py migrate
```

Import product data:

```bash
python manage.py import_products
```

Sync inventory:

```bash
python manage.py sync_inventory
```

Run the app:

```bash
python manage.py runserver
```

## Environment Variables

Local secrets belong in `.env`. Do not commit `.env`.

Expected variables:

```env
DJANGO_SECRET_KEY=your-secret-key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-3.1-flash-lite
```

`smart_grocery/settings.py` loads `.env` manually and exposes `settings.GEMINI_API_KEY` and `settings.GEMINI_MODEL`.

## Git Hygiene

Keep these out of commits:

- `.env`
- `venv/`
- `db.sqlite3`
- `media/`
- `__pycache__/`
- `*.pyc`
- generated pickle files in `grocery_app/ml_models/*.pkl`

Tracked CSV files are currently treated as seed/training data:

- `products.csv`
- `grocery_app/ml_models/orders.csv`

Ask before removing or ignoring those CSVs because the app/recommender may depend on them.

## Development Notes

- Prefer editing existing Django views/templates/models instead of adding a new framework or app structure.
- Keep migrations committed when model fields change.
- If adding config, put real values in `.env` and safe placeholders in `.env.example`.
- If adding dependencies, update `requirements.txt`.
- If touching Gemini, do not hard-code API keys. Read from `settings`.
- If touching image scanning, keep API keys in settings and mock Gemini in tests.
- If touching recommendation code, note that pickle files are generated and ignored; source CSV/code should remain the canonical input.
- `CustomerOrder.items_json` stores order snapshots, so report and invoice code reads from JSON, not live cart items.

## Validation Checklist

Before finishing a meaningful code change, try:

```bash
python manage.py check
python manage.py test
```

If dependency installation or network access is unavailable, say that clearly in the final response.

For template/UI changes, run the dev server and inspect affected pages when possible.

## Known Gotchas

- The app imports recommendation dependencies at startup through `grocery_app/ml_models/recommender.py`; missing `pandas` or `scikit-learn` can break Django import.
- `media/` contains local uploads/test images and should stay ignored.
- `db.sqlite3` is local state and should stay ignored.
- Some routes are placeholders or duplicated in `grocery_app/urls.py`; avoid broad route cleanup unless the task asks for it.
