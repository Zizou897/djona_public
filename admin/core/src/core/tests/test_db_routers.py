from django.test import SimpleTestCase

from core.db_routers import VendorDbRouter


class VendorDbRouterTest(SimpleTestCase):
    def setUp(self):
        self.router = VendorDbRouter()

    def test_blocks_migrations_on_vendor_db_for_any_app(self):
        self.assertFalse(self.router.allow_migrate('vendor_db', 'app'))
        self.assertFalse(self.router.allow_migrate('vendor_db', 'annonces'))
        self.assertFalse(self.router.allow_migrate('vendor_db', 'auth'))
        self.assertFalse(self.router.allow_migrate('vendor_db', 'moderation'))

    def test_defers_for_other_databases(self):
        self.assertIsNone(self.router.allow_migrate('default', 'app'))
        self.assertIsNone(self.router.allow_migrate('default', 'annonces'))
