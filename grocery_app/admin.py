# admin.py
from django.contrib import admin
from .models import *

admin.site.register(Store)
admin.site.register(Product)
admin.site.register(InventoryItem)
admin.site.register(Offer)
admin.site.register(ShoppingList)
admin.site.register(ShoppingListItem)
admin.site.register(CustomerOrder)
admin.site.register(MonthlyBudget)
