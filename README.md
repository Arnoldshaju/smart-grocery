# Smart Grocery

Smart Grocery is a Django web application for managing a grocery shopping experience between customers and shop owners. It includes product browsing, inventory management, cart and checkout flows, order history, reward points, budget tracking, OCR-based grocery list scanning, and product recommendations.

## Features

- Customer and shop-owner registration/login
- Customer product catalog with search, category filtering, stock indicators, and cart actions
- Cart, checkout, order confirmation, order history, and PDF invoice download
- Reward points that can be earned and redeemed during checkout
- Monthly budget tracker based on customer orders
- Grocery list management
- OCR image scanning for grocery list/item detection
- Gemini-powered grocery list image parsing support through environment variables
- Shop-owner dashboard with inventory count, revenue, order, low-stock, offer, and request metrics
- Inventory management for shop owners
- Offer creation
- Unavailable item request flow
- Monthly sales reports with top products and customers
- TF-IDF based product recommendations during checkout

## Tech Stack

- Python
- Django
- SQLite for local development
- ReportLab for PDF invoices
- Google Gen AI SDK with Gemini 3.1 Flash-Lite for grocery image scanning
- Pandas, NumPy, and scikit-learn for product recommendation logic

## Project Structure

```text
.
├── manage.py
├── products.csv
├── requirements.txt
├── smart_grocery/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
└── grocery_app/
    ├── models.py
    ├── views.py
    ├── urls.py
    ├── admin.py
    ├── management/commands/
    ├── migrations/
    ├── ml_models/
    ├── static/
    ├── templates/
    └── templatetags/
```

## Setup

Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a local environment file:

```bash
cp .env.example .env
```

Update `.env` with your local values:

```env
DJANGO_SECRET_KEY=your-secret-key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-3.1-flash-lite
```

Run migrations:

```bash
python manage.py migrate
```

Import products from `products.csv`:

```bash
python manage.py import_products
```

Sync products into store inventory:

```bash
python manage.py sync_inventory
```

Start the development server:

```bash
python manage.py runserver
```

Open the app at:

```text
http://127.0.0.1:8000/
```

## Gemini Integration

Gemini is configured through environment variables, not hard-coded secrets. Add these values to `.env`:

```env
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-3.1-flash-lite
```

The Django settings file loads `.env` and exposes:

- `settings.GEMINI_API_KEY`
- `settings.GEMINI_MODEL`

The grocery image scanning helper in `grocery_app/views.py` reads those settings when calling Gemini.

## Data and Generated Files

The repository tracks source code, templates, static CSS, migrations, and CSV seed/training data. Local runtime files are intentionally ignored:

- `.env`
- `venv/`
- `db.sqlite3`
- `media/`
- `__pycache__/`
- `*.pyc`
- generated ML pickle files in `grocery_app/ml_models/*.pkl`

Use `.env.example` as the safe template for local configuration.

## Notes

- SQLite is configured for local development.
- Do not commit real API keys, local databases, uploaded media, or virtual environments.
- Grocery-list images are scanned through Gemini, so no local OCR executable is required.
