from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Cart, Category, InventoryItem, Product, Store
from .services.gemini_scanner import GeminiScannerError, scan_grocery_items

User = get_user_model()


def image_upload(content_type="image/jpeg", content=b"image-data"):
    return SimpleUploadedFile("list.jpg", content, content_type=content_type)


@override_settings(GEMINI_API_KEY="test-key", GEMINI_MODEL="gemini-3.1-flash-lite")
class GeminiScannerServiceTests(TestCase):
    @patch("google.genai.Client")
    def test_uses_flash_lite_and_normalizes_structured_items(self, client_class):
        response = Mock(parsed={"items": [" Milk ", "milk", "Brown   Rice"]})
        client_class.return_value.models.generate_content.return_value = response

        result = scan_grocery_items(image_upload())

        self.assertEqual(result, ["milk", "brown rice"])
        call = client_class.return_value.models.generate_content.call_args
        self.assertEqual(call.kwargs["model"], "gemini-3.1-flash-lite")
        self.assertEqual(call.kwargs["config"].response_mime_type, "application/json")

    def test_rejects_unsupported_image_type(self):
        with self.assertRaisesMessage(GeminiScannerError, "JPEG, PNG, or WebP"):
            scan_grocery_items(image_upload(content_type="image/gif"))

    @override_settings(GEMINI_API_KEY="")
    def test_reports_missing_api_key_safely(self):
        with self.assertRaisesMessage(GeminiScannerError, "not configured"):
            scan_grocery_items(image_upload())


class GroceryScannerViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="customer", password="password")
        self.owner = User.objects.create_user(username="owner", password="password")
        self.category = Category.objects.create(name="Dairy")
        self.product = Product.objects.create(
            name="Fresh Milk", category=self.category, mrp="50.00"
        )
        self.store = Store.objects.create(name="Test Store", owner=self.owner)
        self.inventory = InventoryItem.objects.get(store=self.store, product=self.product)
        self.cart = Cart.objects.create(user=self.user, store=self.store)
        self.client.force_login(self.user)

    @patch("grocery_app.views.scan_grocery_items", return_value=["milk", "bread"])
    def test_matches_scanned_items_and_reports_missing_items(self, scan):
        response = self.client.post(reverse("ocr_scanner"), {"image": image_upload()})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fresh Milk")
        self.assertContains(response, "bread")
        scan.assert_called_once()

    @patch("grocery_app.views.scan_grocery_items", return_value=["milk"])
    def test_defaults_to_main_store_if_none_selected(self, scan):
        self.cart.store = None
        self.cart.save(update_fields=["store"])

        response = self.client.post(reverse("ocr_scanner"), {"image": image_upload()})

        self.assertEqual(response.status_code, 200)
        scan.assert_called_once()

    def test_legacy_ocr_route_redirects_to_gemini_scanner(self):
        response = self.client.get(reverse("ocr_upload"))

        self.assertRedirects(response, reverse("ocr_scanner"))

# Create your tests here.
