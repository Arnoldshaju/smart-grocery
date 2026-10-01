from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from grocery_app.models import Product, Store, InventoryItem

class Command(BaseCommand):
    help = "Sync all products into inventory for all stores"

    def handle(self, *args, **kwargs):
        if not Store.objects.exists():
            User = get_user_model()
            admin_user, _ = User.objects.get_or_create(
                username="admin",
                defaults={"email": "admin@example.com", "is_staff": True, "is_superuser": True}
            )
            Store.objects.create(name="Smart Grocery Main Store", owner=admin_user)

        stores = Store.objects.all()
        products = Product.objects.all()

        total_created = 0
        for store in stores:
            existing_pids = set(
                InventoryItem.objects.filter(store=store).values_list('product_id', flat=True)
            )
            items_to_create = [
                InventoryItem(store=store, product=p, quantity=100, price=p.mrp)
                for p in products if p.id not in existing_pids
            ]
            if items_to_create:
                InventoryItem.objects.bulk_create(items_to_create, batch_size=1000)
                total_created += len(items_to_create)

        self.stdout.write(self.style.SUCCESS(f"Inventory synced successfully ({total_created} new items created)."))