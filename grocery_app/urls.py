from django.urls import path
from . import views


urlpatterns = [
    path('', views.landing, name='landing'),

    # Authentication
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboards
    path('dashboard/customer/', views.customer_dashboard, name='customer_dashboard'),
    path('dashboard/shopowner/', views.shopowner_dashboard, name='shopowner_dashboard'),
    path('profile/customer/', views.customer_profile, name='customer_profile'),


    # Customer Core Shopping Tools
    path('ocr-scanner/', views.ocr_scanner, name='ocr_scanner'),
    path("ocr/", views.ocr_upload, name="ocr_upload"),
    path('product-search/', views.product_search_view, name='product_search'),
    path('grocery-list/', views.grocery_list_view, name='grocery_list'),
    path('grocery-list/toggle/<int:item_id>/', views.toggle_grocery_item, name='toggle_grocery_item'),

    #path('grocery-history/', views.grocery_history_view, name='grocery_history'),

    path("orders/", views.customer_order_history, name="order_history"),
    path("orders/<int:order_id>/", views.customer_order_detail, name="order_detail"),
    path('budget/', views.budget_view, name='budget'),
    path('rewards/', views.rewards_view, name='rewards'),
    

    path('api/products/',            views.product_api,        name='product_api'),
    path('api/products/categories/', views.categories_api,     name='categories_api'),
    #path('api/grocery-list/',        views.grocery_list_api,   name='grocery_list_api'),
    path('cart/', views.cart_view, name='cart'),
    path('remove-from-cart/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('api/cart/add/',            views.add_to_cart_ajax,   name='add_to_cart_ajax'),    
    # Offers and Checkout
    path("shopowner/offers/create/", views.create_offer_view, name="create_offer"),
    path('offers/', views.offers_view, name='offers'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('order/confirm/', views.confirm_order, name='confirm_order'),
    path('order/success/<int:order_id>/', views.order_success, name='order_success'),
    path('invoice/<int:order_id>/', views.download_invoice, name='download_invoice'),
    path('admin/offers/', views.admin_offers_view, name='admin_offers'),
    path('orders/', views.orders_view, name='orders'),
    path('reports/', views.reports_view, name='reports'),
    path('indoor-navigation/manage/', views.indoor_navigation_manage_view, name='indoor_navigation_manage'),
    
    path("settings/", views.settings_view, name="settings"),

    path('add-to-list/<int:product_id>/', views.add_to_list, name='add_to_list'),

    # In-store Navigation & Route Optimization
    path('indoor-navigation/', views.indoor_nav_view, name='indoor_nav'),

    # Smart Assistance / Insights
    path('association-recommendations/', views.association_recommendations_view, name='association_recommendations'),
    path('healthy-alternatives/', views.healthy_alternatives_view, name='healthy_alternatives'),
    path('inventory/', views.inventory_view, name='inventory'),
    path('inventory/delete/<int:item_id>/', views.delete_inventory_item, name='delete_inventory_item'),


    # Additional customer support features (Requests for unavailable items)
    path('request-item/', views.request_item_view, name='request_item'),
    path('admin/item-requests/', views.unavailable_requests_view, name='unavailable_requests'),
    

    path('payment/', views.dummy_payment, name='dummy_payment'),

    path('budget-tracker/', views.budget_tracker, name='budget_tracker'),

    path("order/success/<int:order_id>/",views.order_success,name="order_success"),
    path('remove-from-cart/<int:product_id>/', views.remove_from_cart, name='remove_from_cart'),
    path("shop-owner/", views.shop_owner, name="shop_owner"),
    path('shopowner/reports/', views.monthly_reports_view, name='monthly_reports'),



    
]
