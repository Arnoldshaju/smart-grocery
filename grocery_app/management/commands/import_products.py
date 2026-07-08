import csv
from django.core.management.base import BaseCommand
from grocery_app.models import Product, Category


class Command(BaseCommand):
    help = "Import products from products.csv"

    def handle(self, *args, **kwargs):
        file_path = "products.csv"
        products_to_create = []
        skipped = 0

        try:
            with open(file_path, newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)

                for row in reader:

                    # Get or create category
                    category_obj, _ = Category.objects.get_or_create(
                        name=row['Category']
                    )

                    # Skip duplicates (based on name)
                    if Product.objects.filter(name=row['ProductName']).exists():
                        skipped += 1
                        continue

                    product = Product(
                        name=row['ProductName'],
                        category=category_obj,
                        mrp=float(row['Price']) if row['Price'] else 0,
                        offer=float(row['DiscountPrice']) if row['DiscountPrice'] else None,
                        unit=row['quantity_type'],
                        image_url=row['Image_Url'],
                    )

                    products_to_create.append(product)

            Product.objects.bulk_create(products_to_create)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Imported {len(products_to_create)} products successfully!"
                )
            )

            if skipped:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipped {skipped} duplicate products."
                    )
                )

        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR("products.csv not found in project root.")
            )