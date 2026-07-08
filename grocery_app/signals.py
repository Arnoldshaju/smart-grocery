from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Product, InventoryItem, Store


@receiver(post_save, sender=Product)
def create_inventory_for_new_product(sender, instance, created, **kwargs):
    if created:
        # Assuming single store system (or default store)
        store = Store.objects.first()

        if store:
            InventoryItem.objects.get_or_create(
                store=store,
                product=instance,
                defaults={
                    'quantity': 100,
                    'price': instance.mrp,
                }
            )
