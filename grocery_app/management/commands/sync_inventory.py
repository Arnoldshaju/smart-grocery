from django.core.management.base import BaseCommand
from grocery_app.models import Product, Store, InventoryItem

class Command(BaseCommand):
    help = "Sync all products into inventory for all stores"

    def handle(self, *args, **kwargs):
        stores = Store.objects.all()
        products = Product.objects.all()

        for store in stores:
            for product in products:
                InventoryItem.objects.get_or_create(
                    store=store,
                    product=product,
                    defaults={
                        "quantity": 100,
                        "price": product.mrp
                    }
                )

        self.stdout.write(self.style.SUCCESS("Inventory synced successfully"))