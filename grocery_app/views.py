from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User, Group
from django.shortcuts import redirect, render
from django.http import HttpResponseRedirect
from django.urls import reverse
import json
from .ml_models.recommender import recommend_products
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage
from django.db.models import F, Q, Value, Case, When, BooleanField, IntegerField
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import Cart, CartItem, Order
from .models import CustomerOrder
from .models import *


from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import pagesizes
from reportlab.lib.units import inch
from django.http import HttpResponse
from io import BytesIO

LOW_STOCK_THRESHOLD = 5
PAGE_SIZE = 36  # 36 products per page (3-col × 12 rows)

def landing(request):
    return render(request, 'landing.html')

def _ensure_role_groups():
    for g in ['Customer', 'ShopOwner']:
        Group.objects.get_or_create(name=g)

def register_view(request):
    _ensure_role_groups()
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        role = request.POST.get('role', 'Customer')  
        if not username or not password or role not in ['Customer', 'ShopOwner']:
            messages.error(request, 'Please fill all required fields correctly.')
            return render(request, 'register.html')
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken.')
            return render(request, 'register.html')
        user = User.objects.create_user(username=username, email=email, password=password)
        group = Group.objects.get(name=role)
        user.groups.add(group)
        messages.success(request, f'Registered as {role}. Please login.')
        return redirect('login')
    return render(request, 'register.html')

def login_view(request):
    _ensure_role_groups()
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is None:
            messages.error(request, 'Invalid credentials.')
            return render(request, 'login.html')
        login(request, user)
        if user.groups.filter(name='ShopOwner').exists() or user.is_staff:
            return redirect('shopowner_dashboard')
        if user.groups.filter(name='Customer').exists():
            return redirect('customer_dashboard')
    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    messages.info(request, 'Logged out.')
    return redirect('landing')

from django.core.paginator import Paginator
from django.db.models import F, Case, When, Value, BooleanField

@login_required
def customer_dashboard(request):

    store = Store.objects.first()

    qs = (
        InventoryItem.objects
        .filter(store=store)
        .select_related('product', 'product__category')
        .annotate(
            name=F('product__name'),
            mrp=F('product__mrp'),
            category_name=F('product__category__name'),
            image_url=F('product__image_url'),
            is_low_stock=Case(
                When(quantity__gt=0, quantity__lte=LOW_STOCK_THRESHOLD,
                     then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),
            is_out_of_stock=Case(
                When(quantity=0, then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),
        )
        .order_by('product__name')
    )

    paginator = Paginator(qs, 20)  # 20 per page
    page_obj = paginator.get_page(1)

    return render(request, 'customer_dashboard.html', {
        'products': page_obj,
    })


# ─────────────────────────────────────────────────────────────
# 2. Product list API  GET /api/products/
#    Params:
#      page       int    default 1
#      q          str    search term (name or category name)
#      category   str    exact Category.name  e.g. "Dairy"
#      sort       str    name_asc | name_desc | price_asc | price_desc
# ─────────────────────────────────────────────────────────────

@login_required
@require_GET
def product_api(request):
    store = Store.objects.first()

    # Single JOIN from InventoryItem → Product → Category
    # All heavy lifting stays in SQL — no Python-level loops over 7 k rows.
    qs = (
        InventoryItem.objects
        .filter(store=store)
        .select_related('product', 'product__category')   # ← FK traversal
        .annotate(
            _name=F('product__name'),
            _mrp=F('product__mrp'),
            # ── FIX 1: category is a FK; pull the *name* field ──
            _category_name=F('product__category__name'),
            _image_url=F('product__image_url'),
            _expiry_date=F('expiry_date'),
            _is_low_stock=Case(
                When(quantity__gt=0, quantity__lte=LOW_STOCK_THRESHOLD,
                     then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),
            _is_out_of_stock=Case(
                When(quantity=0, then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),
        )
    )

    # ── Search ────────────────────────────────────────────────
    # FIX 1: search on product__category__name (FK → name),
    # not product__category which is an integer FK id.
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(product__name__icontains=q) |
            Q(product__category__name__icontains=q)  # ← fixed
        )

    # ── Category filter ───────────────────────────────────────
    # FIX 2: filter on the FK's name field, not the FK id.
    category = request.GET.get('category', '').strip()
    if category:
        qs = qs.filter(product__category__name__iexact=category)  # ← fixed

    # ── Sort ──────────────────────────────────────────────────
    sort_map = {
        'price_asc':  'product__mrp',
        'price_desc': '-product__mrp',
        'name_asc':   'product__name',
        'name_desc':  '-product__name',
    }
    qs = qs.order_by(sort_map.get(request.GET.get('sort', 'name_asc'), 'product__name'))

    # ── Paginate ──────────────────────────────────────────────
    paginator = Paginator(qs, PAGE_SIZE)
    try:
        page = paginator.page(request.GET.get('page', 1))
    except EmptyPage:
        return JsonResponse({'products': [], 'has_next': False, 'total': paginator.count})

    products = [
        {
            'id':              item.product_id,
            'name':            item._name or '',
            'mrp':             str(item._mrp),
            'category':        item._category_name or '',   # ← name string now
            'image_url':       item._image_url or '',
            'stock_quantity':  item.quantity,
            'expiry_date': item._expiry_date.strftime('%Y-%m-%d') if item._expiry_date else None,
            'is_low_stock':    item._is_low_stock,
            'is_out_of_stock': item._is_out_of_stock,
        }
        for item in page.object_list
    ]

    return JsonResponse({
        'products': products,
        'has_next': page.has_next(),
        'page':     page.number,
        'total':    paginator.count,
    })


# ─────────────────────────────────────────────────────────────
# 3. Category list  GET /api/products/categories/
#    Returns Category.name strings (not IDs).
# ─────────────────────────────────────────────────────────────

@login_required
@require_GET
def categories_api(request):
    categories = (
        Category.objects
        .filter(products__isnull=False)
        .distinct()
        .values('id', 'name')
        .order_by('name')
    )

    return JsonResponse(list(categories), safe=False)


# ─────────────────────────────────────────────────────────────
# 4. Grocery / running list  GET /api/grocery-list/
# ─────────────────────────────────────────────────────────────

@login_required
def grocery_list_api(request):
    return JsonResponse([], safe=False)


# ─────────────────────────────────────────────────────────────
# 5. Add to cart  POST /api/cart/add/
#    FIX 3: returns JSON so the JS fetch handler works correctly.
#    Body: product_id=<int>  quantity=<int>
#
#    Adapt the Cart / CartItem model names below if yours differ.
# ─────────────────────────────────────────────────────────────

@login_required
def customer_profile(request):
    return render(request, 'customer_profile.html', {
        'user': request.user
    })


@login_required
def shopowner_dashboard(request):

    profile = request.user.profile

    

    store = profile.store

    # Inventory Count
    inventory_count = InventoryItem.objects.filter(store=store).count()

    # Active Offers
    now = timezone.now()
    active_offers_count = Offer.objects.filter(
        store=store,
        starts_at__lte=now,
        ends_at__gte=now
    ).count()

    # Today's Orders
    today = timezone.now().date()
    todays_orders = CustomerOrder.objects.filter(
        store=store,
        created_at__date=today
    )

    todays_orders_count = todays_orders.count()
    todays_revenue = todays_orders.aggregate(
        total=Sum("total_amount")
    )["total"] or 0

    # Low Stock (example: less than 10)
    low_stock_count = InventoryItem.objects.filter(
        store=store,
        quantity__lt=10
    ).count()

    # Item Requests
    unavailable_requests_count = ItemRequest.objects.count()

    context = {
        "inventory_count": inventory_count,
        "active_offers_count": active_offers_count,
        "todays_orders_count": todays_orders_count,
        "todays_revenue": todays_revenue,
        "low_stock_count": low_stock_count,
        "unavailable_requests_count": unavailable_requests_count,
    }

    return render(request, "shopowner_dashboard.html", context)






from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages


@login_required
def settings_view(request):

    user = request.user
    profile = user.profile

    if request.method == "POST":

        # Update basic user fields
        user.first_name = request.POST.get("first_name", "")
        user.last_name = request.POST.get("last_name", "")
        user.email = request.POST.get("email", "")

        # Update profile fields
        profile.phone = request.POST.get("phone", "")

        profile.expiry_alerts = True if request.POST.get("expiry_alerts") else False
        profile.refill_reminders = True if request.POST.get("refill_reminders") else False
        profile.offers_notifications = True if request.POST.get("offers_notifications") else False

        user.save()
        profile.save()

        messages.success(request, "Settings updated successfully!")
        return redirect("settings")

    return render(request, "settings.html")

@login_required
def add_to_list(request, product_id):
    # This is just a dummy handler for now
    # Later you can implement real logic to add to user's running grocery list
    # For now, just redirect back to dashboard or same page:
    return HttpResponseRedirect(reverse('customer_dashboard'))


import base64
import json
import re

from django.conf import settings
from django.db.models import Q


def load_gemini_api_key():
    return settings.GEMINI_API_KEY


from .models import InventoryItem


def scan_grocery_list_with_gemini(image_file):
    from google import genai

    api_key = load_gemini_api_key()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set. Add it to .env or export it before starting Django.")

    image_file.seek(0)
    image_bytes = image_file.read()
    mime_type = getattr(image_file, "content_type", None) or "image/jpeg"

    client = genai.Client(api_key=api_key)
    response = client.interactions.create(
        model=settings.GEMINI_MODEL,
        input=[
            {
                "type": "text",
                "text": (
                    "Read this grocery list image. Return only JSON in this "
                    'format: {"items": ["milk", "bread", "rice"]}.'
                ),
            },
            {
                "type": "image",
                "data": base64.b64encode(image_bytes).decode("utf-8"),
                "mime_type": mime_type,
            },
        ],
    )

    output = response.output_text.strip()
    if output.startswith("```"):
        output = re.sub(r"^```(?:json)?\s*|\s*```$", "", output, flags=re.I)

    data = json.loads(output)
    return data.get("items", [])


@login_required
def ocr_scanner(request):
    matched_items = []
    not_found = []
    extracted_words = []
    error = None

    if request.method == "POST" and request.FILES.get("image"):
        image_file = request.FILES["image"]

        try:
            extracted_words = scan_grocery_list_with_gemini(image_file)
        except Exception as exc:
            error = f"Could not scan image with Gemini: {exc}"
            extracted_words = []

        extracted_words = [
            item.lower().strip()
            for item in extracted_words
            if isinstance(item, str) and item.strip()
        ]
        extracted_words = list(dict.fromkeys(extracted_words))

        cart, _ = Cart.objects.get_or_create(user=request.user)
        store = cart.store

        if store is None:
            error = "Please select a store before using OCR scanner."
        elif extracted_words:
            query = Q()
            for word in extracted_words:
                query |= Q(product__name__icontains=word)
                query |= Q(product__category__name__icontains=word)

            matched_items = InventoryItem.objects.filter(
                store=store
            ).filter(query).select_related("product").distinct()

            matched_product_names = [
                item.product.name.lower() for item in matched_items
            ]

            for word in extracted_words:
                if not any(word in name for name in matched_product_names):
                    not_found.append(word)

    return render(request, "ocr_scanner.html", {
        "matched_items": matched_items,
        "not_found": not_found,
        "extracted_words": extracted_words,
        "error": error,
    })

from django.shortcuts import render
from .ocr_utils import extract_text
from django.core.files.storage import FileSystemStorage


def ocr_upload(request):
    extracted_text = ""

    if request.method == "POST" and request.FILES.get("image"):
        image = request.FILES["image"]

        fs = FileSystemStorage()
        filename = fs.save(image.name, image)
        image_path = fs.path(filename)

        extracted_text = extract_text(image_path)

    return render(request, "ocr_upload.html", {
        "extracted_text": extracted_text
    })



@login_required
def product_search_view(request):
    from .models import InventoryItem, ShoppingList
    from django.db.models import Q

    query = request.GET.get('q', '').strip()

    inventory_items = InventoryItem.objects.filter(quantity__gt=0).select_related('product')

    if query:
        inventory_items = inventory_items.filter(
            Q(product__name__icontains=query) |
            Q(product__category__name__icontains=query)
        )

    products = []
    LOW_STOCK_THRESHOLD = 5

    for item in inventory_items:
        product = item.product
        product.stock_quantity = item.quantity
        product.is_low_stock = item.quantity <= LOW_STOCK_THRESHOLD
        products.append(product)

    # Grocery list (for sidebar)
    running_list = ShoppingList.objects.filter(
        user=request.user
    ).order_by('-created_at').first()

    grocery_list = running_list.items.all() if running_list else []

    return render(request, 'customer_dashboard.html', {
        'products': products,
        'grocery_list': grocery_list,
        'search_query': query,
    })

from .models import ShoppingList, ShoppingListItem, Product
from django.shortcuts import render, redirect, get_object_or_404

def grocery_list_view(request):
    shopping_list, created = ShoppingList.objects.get_or_create(
        user=request.user,
        title="My Grocery List"
    )

    items = shopping_list.items.all()

    if request.method == 'POST':
        name = request.POST.get('name')
        product_id = request.POST.get('product')
        quantity = request.POST.get('quantity')

        # FIX: default quantity
        if not quantity:
            quantity = "1"

        product = None
        if product_id:
            product = Product.objects.get(id=product_id)

        if product:
            ShoppingListItem.objects.create(
                shopping_list=shopping_list,
                product=product,
                quantity=quantity
            )

        elif name:
            ShoppingListItem.objects.create(
                shopping_list=shopping_list,
                custom_name=name,
                quantity=quantity
            )

        return redirect('grocery_list')

    products = Product.objects.all()

    return render(request, 'grocery_list.html', {
        'shopping_list': shopping_list,
        'items': items,
        'products': products
    })


def toggle_grocery_item(request, item_id):
    item = get_object_or_404(ShoppingListItem, id=item_id, list__user=request.user)
    item.checked = not item.checked
    item.save()
    return redirect('grocery_list')





from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from .models import CustomerOrder


@login_required
def customer_order_history(request):
    orders = (
        CustomerOrder.objects
        .filter(user=request.user)
        .order_by("-created_at")
    )

    return render(request, "order_history.html", {
        "orders": orders
    })

@login_required
def customer_order_detail(request, order_id):
    order = get_object_or_404(
        CustomerOrder,
        id=order_id,
        user=request.user
    )

    return render(request, "order_detail.html", {
        "order": order,
        "items": order.items_json
    })

@login_required
def budget_view(request):
    return render(request, 'budget.html')

@login_required
def rewards_view(request):
    return render(request, 'rewards.html')

@login_required
def offers_view(request):
    return render(request, 'offers.html')

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Offer, InventoryItem

@login_required
def create_offer_view(request):

    # 🔥 JUST LOAD ALL INVENTORY ITEMS
    inventory_items = (
        InventoryItem.objects
        .select_related("product", "store")
        .order_by("product__name")
    )

    if request.method == "POST":
        product_id = request.POST.get("product")
        title = request.POST.get("title")
        discount = request.POST.get("discount_percent")
        starts_at = request.POST.get("starts_at")
        ends_at = request.POST.get("ends_at")

        # find inventory item
        inventory_item = InventoryItem.objects.filter(product_id=product_id).first()

        if inventory_item:
            Offer.objects.create(
                store=inventory_item.store,   # use that inventory's store
                product_id=product_id,
                title=title,
                discount_percent=discount,
                starts_at=starts_at,
                ends_at=ends_at
            )

    return render(request, "create_offer.html", {
        "inventory_items": inventory_items
    })



from django.contrib import messages
from django.shortcuts import render, redirect



from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from .models import Store, Product, InventoryItem

@login_required
def inventory_view(request):
    from .models import Store, Product, InventoryItem
    from django.shortcuts import get_object_or_404

    store, created = Store.objects.get_or_create(
    owner=request.user,
    defaults={
        'name': 'Main Store'
    }
)

    inventory_items = InventoryItem.objects.filter(store=store).select_related('product')
    products = Product.objects.all()

    edit_item = None
    edit_id = request.GET.get('edit')
    if edit_id:
        edit_item = get_object_or_404(InventoryItem, id=edit_id, store=store)

    if request.method == 'POST':
        product_id = request.POST['product']
        quantity = int(request.POST['quantity'])
        price = float(request.POST['price'])
        expiry_date = request.POST.get('expiry_date') or None
        item_id = request.POST.get('item_id')

        product = get_object_or_404(Product, id=product_id)

        if item_id:
            # UPDATE
            item = get_object_or_404(InventoryItem, id=item_id, store=store)
            item.product = product
            item.quantity = quantity
            item.price = price
            item.expiry_date = expiry_date
            item.save()
        else:
            # CREATE
            InventoryItem.objects.create(
                store=store,
                product=product,
                quantity=quantity,
                price=price,
                expiry_date=expiry_date
            )

        return redirect('inventory')

    return render(request, 'inventory.html', {
        'store': store,
        'inventory_items': inventory_items,
        'products': products,
        'edit_item': edit_item
    })


@login_required
def delete_inventory_item(request, item_id):
    from .models import InventoryItem
    item = InventoryItem.objects.filter(id=item_id).first()
    if item:
        item.delete()
    return redirect('inventory')


@login_required
def admin_offers_view(request):
    # TODO: implement actual offers management view
    return render(request, 'admin_offers.html')

@login_required
def orders_view(request):
    return render(request, 'orders.html')

@login_required
def reports_view(request):
    return render(request, 'reports.html')


from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, Count, Avg
from django.db.models.functions import TruncDate
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import CustomerOrder
import json
from collections import defaultdict


@login_required
def monthly_reports_view(request):

    profile = request.user.profile
    store = profile.store

    # =====================================
    # 🔥 ALL-TIME STATS
    # =====================================
    all_orders = CustomerOrder.objects.filter(store=store)

    total_orders = all_orders.count()

    total_revenue = all_orders.aggregate(
        total=Sum("total_amount")
    )["total"] or 0

    avg_order_value = all_orders.aggregate(
        avg=Avg("total_amount")
    )["avg"] or 0


    # =====================================
    # 🔥 LAST 30 DAYS
    # =====================================
    today = timezone.now().date()
    start_date = today - timedelta(days=29)

    last_30_orders = all_orders.filter(
        created_at__date__gte=start_date
    )

    # New customers
    new_customers = (
        last_30_orders
        .values("user")
        .distinct()
        .count()
    )


    # =====================================
    # 📊 DAILY TREND DATA
    # =====================================
    daily_data = (
        last_30_orders
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            order_count=Count("id"),
            revenue=Sum("total_amount")
        )
    )

    daily_dict = {d["day"]: d for d in daily_data}

    labels = []
    order_counts = []
    revenue_data = []

    for i in range(30):
        day = start_date + timedelta(days=i)
        labels.append(day.strftime("%d %b"))

        if day in daily_dict:
            order_counts.append(daily_dict[day]["order_count"])
            revenue_data.append(float(daily_dict[day]["revenue"] or 0))
        else:
            order_counts.append(0)
            revenue_data.append(0)


    # =====================================
    # 🥇 TOP PRODUCTS (FROM items_json)
    # =====================================
    product_counter = defaultdict(int)

    for order in last_30_orders:
        for item in order.items_json:
            name = item.get("name")
            qty = int(item.get("quantity", 0))
            product_counter[name] += qty

    sorted_products = sorted(
        product_counter.items(),
        key=lambda x: x[1],
        reverse=True
    )

    top_products = sorted_products[:5]

    highest_product = top_products[0][0] if top_products else "N/A"

    pie_labels = [p[0] for p in top_products]
    pie_data = [p[1] for p in top_products]


    # =====================================
    # 👑 TOP USERS
    # =====================================
    top_users = (
        last_30_orders
        .values("user__username")
        .annotate(total_spent=Sum("total_amount"))
        .order_by("-total_spent")[:5]
    )


    # =====================================
    # 📈 GROWTH CALCULATION
    # =====================================
    previous_start = start_date - timedelta(days=30)

    previous_orders = all_orders.filter(
        created_at__date__gte=previous_start,
        created_at__date__lt=start_date
    )

    prev_revenue = previous_orders.aggregate(
        total=Sum("total_amount")
    )["total"] or 0

    prev_order_count = previous_orders.count()

    if prev_revenue > 0:
        revenue_growth = round(
            ((total_revenue - prev_revenue) / prev_revenue) * 100, 2
        )
    else:
        revenue_growth = 100 if total_revenue > 0 else 0

    if prev_order_count > 0:
        order_growth = round(
            ((total_orders - prev_order_count) / prev_order_count) * 100, 2
        )
    else:
        order_growth = 100 if total_orders > 0 else 0


    # =====================================
    # 📦 CONTEXT
    # =====================================
    context = {
        "total_orders": total_orders,
        "total_revenue": round(total_revenue, 2),
        "avg_order_value": round(avg_order_value, 2),
        "new_customers": new_customers,

        "labels": json.dumps(labels),
        "order_counts": json.dumps(order_counts),
        "revenue_data": json.dumps(revenue_data),

        "top_products": top_products,
        "top_users": top_users,

        "highest_product": highest_product,
        "revenue_growth": revenue_growth,
        "order_growth": order_growth,

        "pie_labels": json.dumps(pie_labels),
        "pie_data": json.dumps(pie_data),
    }

    return render(request, "monthly_reports.html", context)


@login_required
def indoor_navigation_manage_view(request):
    return render(request, 'indoor_navigation_manage.html')

@login_required
def indoor_nav_view(request):
    return render(request, 'indoor_nav.html')

@login_required
def association_recommendations_view(request):
    return render(request, 'association_recommendations.html')

@login_required
def healthy_alternatives_view(request):
    return render(request, 'healthy_alternatives.html')

@login_required
def unavailable_requests_view(request):
    from .models import ItemRequest

    requests = ItemRequest.objects.all().order_by('-created_at')

    return render(request, 'unavailable_requests.html', {
        'requests': requests
    })


@login_required
def request_item_view(request):
    from .models import ItemRequest

    if request.method == 'POST':
        item_name = request.POST.get('item_name')
        note = request.POST.get('note', '')

        if item_name:
            ItemRequest.objects.create(
                user=request.user,
                item_name=item_name,
                note=note
            )

        return redirect('customer_dashboard')

    return render(request, 'request_item.html')



@login_required
@require_POST
def add_to_cart_ajax(request):
    product_id = int(request.POST.get("product_id"))
    quantity = max(1, int(request.POST.get("quantity", 1)))

    store = Store.objects.first()

    inventory_item = get_object_or_404(
        InventoryItem,
        store=store,
        product_id=product_id,
        quantity__gt=0
    )

    cart, _ = Cart.objects.get_or_create(
        user=request.user,
        defaults={"store": store}
    )

    if cart.store is None:
        cart.store = store
        cart.save(update_fields=["store"])

    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product_id=product_id,
        defaults={"quantity": quantity}
    )

    if not created:
        cart_item.quantity += quantity
        cart_item.save(update_fields=["quantity"])

    return JsonResponse({"ok": True})

@login_required
def cart_view(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)

    items = cart.items.select_related("product")
    total = sum(item.subtotal() for item in items)

    return render(request, "cart.html", {
        "items": items,
        "total": total
    })


@login_required
@require_POST
def remove_from_cart(request, product_id):
    cart = get_object_or_404(Cart, user=request.user)

    CartItem.objects.filter(
        cart=cart,
        product_id=product_id
    ).delete()

    # Support redirecting back to checkout when removing from within the checkout page
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url == 'checkout':
        return redirect("checkout")
    return redirect("cart")


@login_required
def checkout_view(request):
    cart = get_object_or_404(Cart, user=request.user)

    items = cart.items.select_related("product")
    total = sum(item.subtotal() for item in items)

    if not items:
        return redirect("cart")

    # 🔥 Build recommendations per cart item, enriched with real DB product data
    recommendations = {}

    # Pre-fetch all products into a name→product mapping for quick lookup
    all_products = {p.name.lower(): p for p in Product.objects.all()}

    for item in items:
        product_name = item.product.name
        recs = recommend_products(product_name, top_n=5)

        enriched_recs = []
        for rec in recs:
            rec_name_lower = rec.get('ProductName', '').lower()
            db_product = all_products.get(rec_name_lower)

            # Only include recommendations that exist in the DB (so they can be added to cart)
            if db_product:
                rec['id'] = db_product.id
                rec['mrp'] = str(db_product.mrp)
                rec['image_url'] = db_product.image_url or ''
                enriched_recs.append(rec)

        recommendations[item.id] = enriched_recs

    return render(request, "checkout.html", {
        "items": items,
        "total": total,
        "recommendations": recommendations,
    })

@login_required
@require_POST
def confirm_order(request):
    cart = get_object_or_404(Cart, user=request.user)

    if not cart.items.exists():
        return redirect("cart")

    items_data = []
    total = 0

    for item in cart.items.select_related("product"):
        subtotal = item.subtotal()
        total += subtotal

        items_data.append({
            "name": item.product.name,
            "quantity": item.quantity,
            "price": float(item.product.mrp),
            "subtotal": float(subtotal),
        })

    # 🎁 GET REDEEM POINTS FROM FORM
    redeem_points = int(request.POST.get("redeem_points", 0))
    profile = request.user.profile

    # Safety checks
    if redeem_points > profile.reward_points:
        redeem_points = profile.reward_points

    if redeem_points > total:
        redeem_points = int(total)

    # Apply discount
    final_total = total - redeem_points

    # 🔥 Create Order
    order = CustomerOrder.objects.create(
        user=request.user,
        store=cart.store,
        items_json=items_data,
        total_amount=final_total
    )

    # 🎁 Deduct redeemed points
    profile.reward_points -= redeem_points

    # 🎁 Add new earned points (1 per ₹100 spent)
    points_earned = int(final_total // 100)
    profile.reward_points += points_earned

    profile.save()

    cart.items.all().delete()

    return redirect("order_success", order_id=order.id)


@login_required
def order_success(request, order_id):
    order = get_object_or_404(CustomerOrder, id=order_id, user=request.user)
    points_earned = int(order.total_amount // 100)

    return render(request, "order_success.html", {
        "order": order
    })


@login_required
def dummy_payment(request):
    cart = get_object_or_404(Cart, user=request.user)

    if not cart.items.exists():
        return redirect('cart')

    context = {
        'cart': cart,
        'total': cart.total_price(),
    }

    return render(request, 'dummy_payment.html', context)


from datetime import datetime
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .models import MonthlyBudget, CustomerOrder


@login_required
def budget_tracker(request):
    now = datetime.now()
    month = now.month
    year = now.year

    budget = MonthlyBudget.objects.filter(
        user=request.user,
        month=month,
        year=year
    ).first()

    # Orders this month
    orders = CustomerOrder.objects.filter(
        user=request.user,
        created_at__month=month,
        created_at__year=year
    )

    # Total spent this month
    total_spent = orders.aggregate(total=Sum('total_amount'))['total'] or 0

    # ✅ Collect all products from JSONField
    all_products = []
    for order in orders:
        if order.items_json:
            all_products.extend(order.items_json)

    # Budget calculations
    remaining = 0
    overspent = False

    if budget:
        remaining = budget.budget_amount - total_spent
        overspent = total_spent > budget.budget_amount

    # Handle budget update
    if request.method == "POST":
        amount = request.POST.get("budget")

        MonthlyBudget.objects.update_or_create(
            user=request.user,
            month=month,
            year=year,
            defaults={"budget_amount": amount}
        )

        return redirect("budget_tracker")

    return render(request, "budget_tracker.html", {
        "budget": budget,
        "total_spent": total_spent,
        "remaining": remaining,
        "overspent": overspent,
        "products": all_products,
        "month": month,
        "year": year
    })




from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from io import BytesIO
from .models import CustomerOrder


def download_invoice(request, order_id):
    order = get_object_or_404(
        CustomerOrder,
        id=order_id,
        user=request.user
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)

    elements = []
    styles = getSampleStyleSheet()

    # =========================
    # HEADER
    # =========================
    elements.append(Paragraph("<b>SMART GROCERY</b>", styles["Title"]))
    elements.append(Spacer(1, 0.2 * inch))

    elements.append(Paragraph(f"Invoice No: #{order.id}", styles["Normal"]))
    elements.append(Paragraph(f"Date: {order.created_at.strftime('%d %B %Y')}", styles["Normal"]))
    elements.append(Paragraph(f"Customer: {order.user.username}", styles["Normal"]))
    elements.append(Spacer(1, 0.4 * inch))

    # =========================
    # TABLE DATA
    # =========================
    data = [["Product", "Quantity", "Unit Price", "Subtotal"]]

    for item in order.items_json:
        qty = item["quantity"]
        subtotal = float(item["subtotal"])
        unit_price = round(subtotal / qty, 2) if qty else 0

        data.append([
            item["name"],
            str(qty),
            f"Rs{unit_price}",
            f"Rs{subtotal}"
        ])

    # Add total row
    data.append(["", "", "Total", f"Rs{order.total_amount}"])

    table = Table(data, colWidths=[2.5*inch, 1*inch, 1*inch, 1.2*inch])

    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (-1, -1), (-1, -1), colors.whitesmoke),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 0.5 * inch))

    # =========================
    # FOOTER
    # =========================
    elements.append(Paragraph("Thank you for shopping with Smart Grocery!", styles["Normal"]))
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph("This is a system-generated invoice.", styles["Normal"]))

    doc.build(elements)

    buffer.seek(0)

    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="invoice_{order.id}.pdf"'

    return response

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import CustomerOrder

@login_required
def shop_owner(request):
    orders = CustomerOrder.objects.all().order_by('-created_at')
    return render(request, "shop_owner_orders.html", {
        "orders": orders
    })


@login_required
def indoor_nav_view(request):
    """Interactive indoor store navigation map page."""
    return render(request, 'indoor_nav.html')


@login_required
def indoor_navigation_manage_view(request):
    """Admin/shop-owner view for managing indoor navigation zones (placeholder)."""
    return render(request, 'indoor_nav.html')
