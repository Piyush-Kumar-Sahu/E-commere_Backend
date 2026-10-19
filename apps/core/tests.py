from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User, Address
from apps.catalogue.models import Category, Product, ProductVariant
from apps.orders.models import Order, OrderItem
from apps.reviews.models import Review
from apps.promotions.models import Coupon

class ModiecommersBackendTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create Admin
        self.admin_user, _ = User.objects.get_or_create(
            email='admin@modiecommers.com',
            defaults={
                'username': 'admin',
                'is_staff': True,
                'is_superuser': True,
                'role': User.Role.ADMIN,
                'is_verified': True,
                'is_active': True,
            }
        )
        self.admin_user.set_password('AdminPassword123!')
        self.admin_user.save()

        # Create Customers (verified for checkout/reviews)
        self.customer1 = User.objects.create_user(
            email='customer1@example.com',
            password='CustomerPassword123!',
            username='customer1',
            is_verified=True
        )
        self.customer2 = User.objects.create_user(
            email='customer2@example.com',
            password='CustomerPassword123!',
            username='customer2',
            is_verified=True
        )

        # Create Category & Product
        self.category = Category.objects.create(name='Rings', slug='rings')
        self.product = Product.objects.create(
            name='Test Solitaire Ring',
            slug='test-solitaire-ring',
            sku='TEST-RNG-01',
            category=self.category,
            base_price=Decimal('50000.00'),
            sale_price=Decimal('45000.00'),
            is_active=True
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            variant_type='Ring Size',
            variant_name='Size 7',
            sku='TEST-RNG-01-S7',
            price_adjustment=Decimal('1000.00'),
            stock_quantity=5,
            is_active=True
        )

        # Create Coupon
        self.coupon = Coupon.objects.create(
            code='SAVE10',
            discount_type=Coupon.DiscountType.PERCENTAGE,
            discount_value=Decimal('10.00'),
            minimum_order_amount=Decimal('10000.00'),
            is_active=True
        )

    def test_customer_registration_and_login(self):
        from apps.accounts.models import EmailVerificationOTP

        # 1. Registration creates an unverified account and generates OTP
        reg_response = self.client.post('/api/v1/accounts/register/', {
            'email': 'newcustomer@example.com',
            'password': 'SecurePassword123!',
            'password_confirm': 'SecurePassword123!',
            'first_name': 'Neha',
            'last_name': 'Mehta'
        })
        self.assertEqual(reg_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(reg_response.data['requires_verification'])
        self.assertNotIn('tokens', reg_response.data)

        # 2. Unverified customer cannot log in
        login_unverified = self.client.post('/api/v1/accounts/login/', {
            'email': 'newcustomer@example.com',
            'password': 'SecurePassword123!'
        })
        self.assertEqual(login_unverified.status_code, status.HTTP_400_BAD_REQUEST)

        # 3. Verify OTP
        new_user = User.objects.get(email='newcustomer@example.com')
        otp_instance, raw_code = EmailVerificationOTP.generate_for_user(new_user)
        verify_response = self.client.post('/api/v1/accounts/verify-email/', {
            'email': 'newcustomer@example.com',
            'otp': raw_code
        })
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)
        self.assertIn('tokens', verify_response.data)

        # 4. Verified user can now log in
        login_response = self.client.post('/api/v1/accounts/login/', {
            'email': 'newcustomer@example.com',
            'password': 'SecurePassword123!'
        })
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn('access', login_response.data)

    def test_product_catalogue_api(self):
        response = self.client.get('/api/v1/catalogue/products/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data['results']) >= 1)

        detail_response = self.client.get(f'/api/v1/catalogue/products/{self.product.slug}/')
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(str(detail_response.data['current_price'])), Decimal('45000.00'))

    def test_cart_operations_and_stock_validation(self):
        self.client.force_authenticate(user=self.customer1)

        # Add within stock (2 units)
        add_response = self.client.post('/api/v1/cart/items/', {
            'product_id': self.product.id,
            'variant_id': self.variant.id,
            'quantity': 2
        })
        self.assertEqual(add_response.status_code, status.HTTP_201_CREATED)

        # Attempt to add exceeding stock (available 5, asking +10)
        exceed_response = self.client.post('/api/v1/cart/items/', {
            'product_id': self.product.id,
            'variant_id': self.variant.id,
            'quantity': 10
        })
        self.assertEqual(exceed_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_checkout_atomic_order_creation_and_stock_decrement(self):
        self.client.force_authenticate(user=self.customer1)

        # Add 2 units of variant (initial stock = 5)
        self.client.post('/api/v1/cart/items/', {
            'product_id': self.product.id,
            'variant_id': self.variant.id,
            'quantity': 2
        })

        checkout_response = self.client.post('/api/v1/orders/checkout/', {
            'customer_email': 'customer1@example.com',
            'customer_phone': '+91 99887 76655',
            'customer_name': 'Customer One',
            'shipping_full_name': 'Customer One',
            'shipping_phone': '+91 99887 76655',
            'shipping_street': '22 Marine Lines',
            'shipping_city': 'Mumbai',
            'shipping_state': 'Maharashtra',
            'shipping_postal_code': '400020',
            'coupon_code': 'SAVE10',
            'payment_method': 'razorpay_demo'
        })
        self.assertEqual(checkout_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(checkout_response.data['success'])

        # Verify stock was decremented from 5 to 3
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, 3)

        # Verify payment record and shipment record exist and are marked demo
        order_num = checkout_response.data['order']['order_number']
        order = Order.objects.get(order_number=order_num)
        self.assertTrue(order.payment_record.is_demo)
        self.assertTrue(order.shipment_record.is_demo)

    def test_verified_purchase_review_enforcement(self):
        # Customer 2 has NOT purchased the product
        self.client.force_authenticate(user=self.customer2)

        # Check eligibility endpoint
        eligibility = self.client.get(f'/api/v1/reviews/eligibility/{self.product.id}/')
        self.assertEqual(eligibility.status_code, status.HTTP_200_OK)
        self.assertFalse(eligibility.data['can_review'])

        # Attempt to submit review without purchasing -> must fail with 400 validation error
        review_submit = self.client.post('/api/v1/reviews/submit/', {
            'product_id': self.product.id,
            'rating': 5,
            'title': 'Fake attempt',
            'comment': 'I never bought this.'
        })
        self.assertEqual(review_submit.status_code, status.HTTP_400_BAD_REQUEST)

    def test_access_control_and_permissions(self):
        # Customer 1 cannot access admin stats
        self.client.force_authenticate(user=self.customer1)
        forbidden_response = self.client.get('/api/v1/admin-ops/dashboard/stats/')
        self.assertEqual(forbidden_response.status_code, status.HTTP_403_FORBIDDEN)

        # Admin CAN access admin stats
        self.client.force_authenticate(user=self.admin_user)
        admin_response = self.client.get('/api/v1/admin-ops/dashboard/stats/')
        self.assertEqual(admin_response.status_code, status.HTTP_200_OK)
        self.assertTrue(admin_response.data['success'])

    def test_allowed_hosts_and_debug_production_safeguards(self):
        from django.conf import settings

        # 1. Verify e-commere-backend.onrender.com is present in ALLOWED_HOSTS
        self.assertIn('e-commere-backend.onrender.com', settings.ALLOWED_HOSTS)

        # 2. Verify local development hosts are preserved
        self.assertIn('localhost', settings.ALLOWED_HOSTS)
        self.assertIn('127.0.0.1', settings.ALLOWED_HOSTS)
        self.assertIn('testserver', settings.ALLOWED_HOSTS)

        # 3. Verify wildcard '*' is strictly forbidden
        self.assertNotIn('*', settings.ALLOWED_HOSTS)

    def test_health_check_endpoints(self):
        # 0. Root minimal health check endpoint at '/'
        root_slash_resp = self.client.get('/')
        self.assertEqual(root_slash_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(root_slash_resp.data['status'], 'ok')
        self.assertEqual(root_slash_resp.data['service'], 'Modiecommers E-commerce API')
        self.assertEqual(root_slash_resp.data['version'], '1.0.0')

        # 1. API health check with database check
        response = self.client.get('/api/v1/health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'ok')
        self.assertEqual(response.data['service'], 'Modiecommers E-commerce API')
        self.assertEqual(response.data['database'], 'connected (PostgreSQL)')

        # 2. Root /health/ alias (Render health check path)
        root_resp = self.client.get('/health/')
        self.assertEqual(root_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(root_resp.data['status'], 'ok')

        # 3. Root /healthz/ alias
        healthz_resp = self.client.get('/healthz/')
        self.assertEqual(healthz_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(healthz_resp.data['status'], 'ok')

        # 4. Configurable check_db=false liveness probe
        fast_resp = self.client.get('/api/v1/health/?check_db=false')
        self.assertEqual(fast_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(fast_resp.data['status'], 'ok')
        self.assertEqual(fast_resp.data['database'], 'skipped')

    def test_order_search_and_models_q_filter(self):
        # Verify that searching orders by query param uses models.Q without NameError crash
        self.client.force_authenticate(user=self.admin_user)
        resp = self.client.get('/api/v1/orders/?search=NONEXISTENT_QUERY')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_guest_order_detail_retrieval(self):
        # Create an order placed by customer or guest
        order = Order.objects.create(
            order_number='MOD-TEST-GUEST-01',
            customer_email='guest@example.com',
            customer_phone='+91 91234 56789',
            customer_name='Guest User',
            shipping_full_name='Guest User',
            shipping_phone='+91 91234 56789',
            shipping_street='10 Marine Drive',
            shipping_city='Mumbai',
            shipping_state='Maharashtra',
            shipping_postal_code='400021',
            subtotal_amount=Decimal('45000.00'),
            total_amount=Decimal('45000.00')
        )
        # Unauthenticate client (simulate guest user)
        self.client.force_authenticate(user=None)
        resp = self.client.get(f'/api/v1/orders/{order.order_number}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['order_number'], 'MOD-TEST-GUEST-01')

    def test_product_detail_serializer_category_slug_and_name(self):
        resp = self.client.get(f'/api/v1/catalogue/products/{self.product.slug}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data.get('category_slug'), 'rings')
        self.assertEqual(resp.data.get('category_name'), 'Rings')

    def test_admin_role_permission_consistency(self):
        # User with role=ADMIN but is_staff=False, is_superuser=False
        custom_admin = User.objects.create_user(
            email='customadmin@example.com',
            password='AdminPassword123!',
            username='customadmin',
            role=User.Role.ADMIN,
            is_staff=False,
            is_superuser=False,
            is_verified=True
        )
        self.client.force_authenticate(user=custom_admin)
        resp = self.client.get('/api/v1/admin-ops/dashboard/stats/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['success'])

    def test_csv_export_query_param_token_authentication(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        jwt_token = str(RefreshToken.for_user(self.admin_user).access_token)
        # Unauthenticate header and request with ?token= parameter
        self.client.force_authenticate(user=None)
        resp = self.client.get(f'/api/v1/admin-ops/export/orders-csv/?token={jwt_token}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp['Content-Type'], 'text/csv')

