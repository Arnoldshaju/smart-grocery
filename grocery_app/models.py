from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

from django.contrib.auth import get_user_model
User = get_user_model()


# =========================
# STORE
# =========================
class Store(models.Model):
    name = models.CharField(max_length=120)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stores')
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# =========================
# CATEGORY (NEW – IMPORTANT)
# =========================
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        indexes = [models.Index(fields=['name'])]

    def __str__(self):
        return self.name


# =========================
# PRODUCT
# =========================
class Product(models.Model):
    name = models.CharField(max_length=160)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )
    unit = models.CharField(max_length=20, default='unit')
    mrp = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    image_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return self.name


# =========================
# INVENTORY
# =========================
class InventoryItem(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='inventory')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory_items')
    quantity = models.PositiveIntegerField(default=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    expiry_date = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['store', 'product'], name='unique_store_product')
        ]

    def __str__(self):
        return f'{self.product.name} @ {self.store.name}'


# =========================
# USER PROFILE
# =========================
class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('Customer', 'Customer'),
        ('ShopOwner', 'ShopOwner'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default='Customer')
    store = models.ForeignKey(Store, null=True, blank=True, on_delete=models.SET_NULL)
    expiry_alerts = models.BooleanField(default=True)
    refill_reminders = models.BooleanField(default=True)
    offers_notifications = models.BooleanField(default=False)

    phone = models.CharField(max_length=20, blank=True)
    preferred_currency = models.CharField(max_length=8, default='INR')
    reward_points = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f'{self.user.username} ({self.role})'

    @property
    def is_customer(self):
        return self.role == 'Customer'

    @property
    def is_shop_owner(self):
        return self.role == 'ShopOwner'


# =========================
# SHOPPING LIST
# =========================
class ShoppingList(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shopping_lists')
    title = models.CharField(max_length=140, default='My List')
    created_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=50, default='manual')

    def total_items(self):
        return self.items.count()

    def __str__(self):
        return f'{self.title} ({self.user.username})'


class ShoppingListItem(models.Model):
    shopping_list = models.ForeignKey(
        ShoppingList,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL)
    custom_name = models.CharField(max_length=160, blank=True)
    quantity = models.CharField(max_length=40, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)
    checked = models.BooleanField(default=False)

    def __str__(self):
        return self.custom_name or (self.product.name if self.product else "Item")


# =========================
# OFFERS
# =========================
class Offer(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    title = models.CharField(max_length=140)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField()

    def is_active(self):
        now = timezone.now()
        return self.starts_at <= now <= self.ends_at

    def __str__(self):
        return f'{self.title} - {self.product.name}'


# =========================
# ITEM REQUEST
# =========================
class ItemRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    item_name = models.CharField(max_length=150)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.item_name


# =========================
# SIGNALS
# =========================
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_related(sender, instance, created, **kwargs):
    if created:
        profile, _ = UserProfile.objects.get_or_create(
            user=instance,
            defaults={'role': 'Customer'}
        )

        customer_group, _ = Group.objects.get_or_create(name='Customer')
        shopowner_group, _ = Group.objects.get_or_create(name='ShopOwner')

        if profile.role == 'ShopOwner':
            instance.groups.add(shopowner_group)
        else:
            instance.groups.add(customer_group)


@receiver(post_save, sender=Product)
def sync_product_to_inventory(sender, instance, created, **kwargs):
    if created:
        stores = Store.objects.all()
        inventory_items = [
            InventoryItem(
                store=store,
                product=instance,
                quantity=100,
                price=instance.mrp
            )
            for store in stores
        ]
        InventoryItem.objects.bulk_create(inventory_items, ignore_conflicts=True)


@receiver(post_save, sender=Store)
def sync_store_inventory(sender, instance, created, **kwargs):
    if created:
        products = Product.objects.all()
        inventory_items = [
            InventoryItem(
                store=instance,
                product=product,
                quantity=100,
                price=product.mrp
            )
            for product in products
        ]
        InventoryItem.objects.bulk_create(inventory_items, ignore_conflicts=True)

# =========================
# CART
# =========================
class Cart(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='cart'
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='carts'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def total_items(self):
        return self.items.aggregate(total=models.Sum('quantity'))['total'] or 0

    def total_price(self):
        return sum(item.subtotal() for item in self.items.select_related('product'))

    def __str__(self):
        return f'Cart — {self.user.username}'


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='cart_items'
    )
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['cart', 'product'], name='unique_cart_product')
        ]
        ordering = ['added_at']

    def subtotal(self):
        return self.product.mrp * self.quantity

    def __str__(self):
        return f'{self.quantity}x {self.product.name} (Cart: {self.cart.user.username})'
    
class Order(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Paid', 'Paid'),
        ('Cancelled', 'Cancelled'),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='orders'
    )

    store = models.ForeignKey(
        Store,
        on_delete=models.SET_NULL,
        null=True
    )

    # 👇 Store items snapshot here
    items_json = models.JSONField(default=list)

    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Pending'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Order #{self.id} — {self.user.username}'
    

class CustomerOrder(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_orders"
    )

    store = models.ForeignKey(
        Store,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    items_json = models.JSONField()
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"CustomerOrder #{self.id} - {self.user.username}"
    
class MonthlyBudget(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="budgets"
    )

    month = models.IntegerField()   # 1-12
    year = models.IntegerField()

    budget_amount = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'month', 'year')

    def __str__(self):
        return f"{self.user.username} - {self.month}/{self.year}"