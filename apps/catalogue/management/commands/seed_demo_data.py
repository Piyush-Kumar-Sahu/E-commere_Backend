import os
import requests
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.conf import settings
from apps.catalogue.models import Category, Collection, Product, ProductImage, ProductVariant
from apps.promotions.models import Coupon, Banner, StoreSetting
from apps.accounts.models import User
from apps.orders.models import Order, OrderItem, OrderStatusEvent, PaymentRecord, ShipmentRecord
from apps.reviews.models import Review

class Command(BaseCommand):
    help = 'Seeds the database with curated jewellery categories, collections, products, variants, banners, and coupons.'

    def handle(self, *args, **options):
        self.stdout.write("Starting database seeding for Modiecommers...")

        # 1. Initialize Store Settings
        store_settings = StoreSetting.get_settings()
        store_settings.store_name = "Modiecommers Fine Jewellery"
        store_settings.support_email = "care@modiecommers.com"
        store_settings.support_phone = "+91 98765 43210"
        store_settings.store_address = "102, Heritage Diamond Tower, Zaveri Bazaar, Mumbai, Maharashtra 400002"
        store_settings.announcement_bar_text = "Complimentary insured delivery on orders over ₹5,000 | 100% Certified Natural Diamonds & Hallmarked Gold"
        store_settings.free_shipping_threshold = Decimal('5000.00')
        store_settings.save()
        self.stdout.write(self.style.SUCCESS("[OK] Store settings configured."))

        # 2. Categories
        categories_data = [
            {'name': 'Rings', 'slug': 'rings', 'description': 'Handcrafted engagement rings, solitaires, and luxury cocktail bands in 18K and 22K gold.', 'order': 1},
            {'name': 'Necklaces', 'slug': 'necklaces', 'description': 'Regal bridal chokers, layered diamond necklaces, and understated contemporary chains.', 'order': 2},
            {'name': 'Earrings', 'slug': 'earrings', 'description': 'Brilliant diamond studs, chandelier jhumkas, and sleek drops sculpted in precious metals.', 'order': 3},
            {'name': 'Bracelets', 'slug': 'bracelets', 'description': 'Classic diamond tennis bracelets, royal kadas, and delicate charm wristlets.', 'order': 4},
            {'name': 'Pendants', 'slug': 'pendants', 'description': 'Intricately designed solitaires, celestial emblems, and gemstone statement pendants.', 'order': 5},
        ]

        cat_objs = {}
        for c in categories_data:
            obj, _ = Category.objects.update_or_create(
                slug=c['slug'],
                defaults={'name': c['name'], 'description': c['description'], 'display_order': c['order'], 'is_active': True}
            )
            cat_objs[c['slug']] = obj
        self.stdout.write(self.style.SUCCESS("[OK] Categories created."))

        # 3. Collections
        collections_data = [
            {'name': 'The Royal Heritage Suite', 'slug': 'royal-heritage', 'tagline': 'Masterpieces inspired by regal Indian royal courts', 'desc': 'Intricate filigree and handpicked uncut polki diamonds set in 22K yellow gold.', 'featured': True},
            {'name': 'Celestial Solitaires', 'slug': 'celestial-solitaires', 'tagline': 'Timeless radiance for modern daily luxury', 'desc': 'Precision-cut certified natural diamonds designed for eternal brilliance.', 'featured': True},
            {'name': 'Rose Gold Euphoria', 'slug': 'rose-gold-euphoria', 'tagline': 'Warm blushing hues meet modern silhouettes', 'desc': '18K warm rose gold paired with brilliant pavé diamonds and soft morganite.', 'featured': True},
            {'name': 'Imperial Emeralds', 'slug': 'imperial-emeralds', 'tagline': 'Lush Colombian emeralds and South Sea pearls', 'desc': 'Vibrant verdant gemstones reflecting timeless nobility and elegance.', 'featured': False},
        ]

        col_objs = {}
        for col in collections_data:
            obj, _ = Collection.objects.update_or_create(
                slug=col['slug'],
                defaults={'name': col['name'], 'tagline': col['tagline'], 'description': col['desc'], 'is_featured': col['featured'], 'is_active': True}
            )
            col_objs[col['slug']] = obj
        self.stdout.write(self.style.SUCCESS("[OK] Collections created."))

        # Helper to fetch or create a local image
        def save_product_image(product, image_url, alt_text, is_primary=False, display_order=0):
            try:
                resp = requests.get(image_url, timeout=5)
                if resp.status_code == 200:
                    ext = "jpg"
                    fname = f"{product.slug}_{display_order}.{ext}"
                    img_obj, created = ProductImage.objects.get_or_create(
                        product=product,
                        display_order=display_order,
                        defaults={'alt_text': alt_text, 'is_primary': is_primary}
                    )
                    img_obj.image.save(fname, ContentFile(resp.content), save=True)
                    return img_obj
            except Exception as e:
                self.stdout.write(f"Notice: Image fetch skipped for {product.slug}: {e}")
            return None

        # 4. Products Data
        products_data = [
            {
                'name': 'Aura Diamond Solitaire Engagement Ring',
                'slug': 'aura-diamond-solitaire-ring',
                'sku': 'MOD-RNG-001',
                'category': 'rings',
                'collection': 'celestial-solitaires',
                'base_price': Decimal('89999.00'),
                'sale_price': Decimal('79999.00'),
                'metal_type': Product.MetalType.WHITE_GOLD,
                'metal_purity': Product.MetalPurity.PURITY_18K,
                'gemstone': '1.02 ct VVS1 Lab-Grown & Natural Diamond',
                'weight_grams': Decimal('3.85'),
                'short_description': 'A breathtaking 18K white gold solitaire ring showcasing a brilliant round-cut centre diamond in a 6-prong platinum crown.',
                'description': 'Handcrafted by our master diamond setters, the Aura Solitaire represents the pinnacle of refined elegance. Each diamond is hand-selected for exceptional clarity and cut grade, ensuring intense fire and dispersion under any light. The tapered band offers a featherlight, comfortable fit for lifelong daily wear.',
                'is_featured': True,
                'is_new_arrival': True,
                'is_bestseller': True,
                'variants': [
                    {'type': 'Ring Size', 'name': 'Size 6 (16.5 mm)', 'sku': 'MOD-RNG-001-S6', 'price_adj': Decimal('0.00'), 'stock': 8},
                    {'type': 'Ring Size', 'name': 'Size 7 (17.3 mm)', 'sku': 'MOD-RNG-001-S7', 'price_adj': Decimal('0.00'), 'stock': 12},
                    {'type': 'Ring Size', 'name': 'Size 8 (18.1 mm)', 'sku': 'MOD-RNG-001-S8', 'price_adj': Decimal('1500.00'), 'stock': 6},
                ],
                'images': [
                    {'url': 'https://images.unsplash.com/photo-1605100804763-247f67b3557e?w=800&auto=format&fit=crop&q=80', 'alt': 'Aura Solitaire Diamond Ring front view', 'is_primary': True},
                    {'url': 'https://images.unsplash.com/photo-1603561591411-07134e71a2a9?w=800&auto=format&fit=crop&q=80', 'alt': 'Aura Solitaire Ring on hand', 'is_primary': False},
                ]
            },
            {
                'name': 'Noor Emerald & Polki Royal Bridal Necklace',
                'slug': 'noor-emerald-polki-necklace',
                'sku': 'MOD-NCK-002',
                'category': 'necklaces',
                'collection': 'royal-heritage',
                'base_price': Decimal('285000.00'),
                'sale_price': Decimal('249999.00'),
                'metal_type': Product.MetalType.YELLOW_GOLD,
                'metal_purity': Product.MetalPurity.PURITY_22K,
                'gemstone': 'Zambian Emeralds & Certified Uncut Polki',
                'weight_grams': Decimal('52.40'),
                'short_description': 'An opulent 22K yellow gold bridal necklace featuring deep green emerald teardrops and radiant polki diamonds.',
                'description': 'Drawing deep inspiration from royal Mughal dynasties, the Noor Choker marries master meenakari enamelling on the reverse with brilliant polki diamonds on the face. Finished with delicate South Sea pearl tassels, it stands as an enduring heirloom destined for cherished generations.',
                'is_featured': True,
                'is_new_arrival': False,
                'is_bestseller': True,
                'variants': [
                    {'type': 'Chain Length', 'name': 'Adjustable Choker (14-16 in)', 'sku': 'MOD-NCK-002-CHK', 'price_adj': Decimal('0.00'), 'stock': 3},
                    {'type': 'Chain Length', 'name': 'Grand Bridal Length (18 in)', 'sku': 'MOD-NCK-002-BRD', 'price_adj': Decimal('12000.00'), 'stock': 2},
                ],
                'images': [
                    {'url': 'https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=800&auto=format&fit=crop&q=80', 'alt': 'Noor Emerald & Polki Necklace', 'is_primary': True},
                    {'url': 'https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?w=800&auto=format&fit=crop&q=80', 'alt': 'Noor Necklace detail view', 'is_primary': False},
                ]
            },
            {
                'name': 'Serenade Rose Gold Pavé Drop Earrings',
                'slug': 'serenade-rose-gold-drop-earrings',
                'sku': 'MOD-EAR-003',
                'category': 'earrings',
                'collection': 'rose-gold-euphoria',
                'base_price': Decimal('45000.00'),
                'sale_price': Decimal('39999.00'),
                'metal_type': Product.MetalType.ROSE_GOLD,
                'metal_purity': Product.MetalPurity.PURITY_18K,
                'gemstone': '0.78 ct Brilliant Cut Diamonds',
                'weight_grams': Decimal('6.20'),
                'short_description': 'Delicate 18K rose gold drop earrings encrusted with shimmering micro-pavé diamonds with smooth movement.',
                'description': 'Designed for seamless day-to-evening transitions, these Serenade drops catch light with every gesture. Crafted in hypoallergenic 18K rose gold with secure push-back clasps, offering effortless grace and contemporary glamour.',
                'is_featured': True,
                'is_new_arrival': True,
                'is_bestseller': False,
                'variants': [
                    {'type': 'Backing Type', 'name': 'Comfort Push Back', 'sku': 'MOD-EAR-003-PB', 'price_adj': Decimal('0.00'), 'stock': 15},
                    {'type': 'Backing Type', 'name': 'Screw Back Locking', 'sku': 'MOD-EAR-003-SB', 'price_adj': Decimal('1200.00'), 'stock': 9},
                ],
                'images': [
                    {'url': 'https://images.unsplash.com/photo-1635767798638-3e25273a8236?w=800&auto=format&fit=crop&q=80', 'alt': 'Serenade Rose Gold Drop Earrings', 'is_primary': True},
                    {'url': 'https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?w=800&auto=format&fit=crop&q=80', 'alt': 'Serenade Earrings Pair', 'is_primary': False},
                ]
            },
            {
                'name': 'Elysian Diamond Tennis Bracelet',
                'slug': 'elysian-diamond-tennis-bracelet',
                'sku': 'MOD-BRC-004',
                'category': 'bracelets',
                'collection': 'celestial-solitaires',
                'base_price': Decimal('120000.00'),
                'sale_price': None,
                'metal_type': Product.MetalType.WHITE_GOLD,
                'metal_purity': Product.MetalPurity.PURITY_18K,
                'gemstone': '3.20 ct Round Brilliant Diamonds',
                'weight_grams': Decimal('14.80'),
                'short_description': 'A continuous stream of hand-calibrated brilliant round diamonds set in four-prong 18K white gold baskets.',
                'description': 'An indispensable icon of fine jewellery collections. The Elysian Tennis Bracelet features precision-matched diamonds that cascade fluidly around the wrist, secured by a double-latching safety clasp.',
                'is_featured': True,
                'is_new_arrival': False,
                'is_bestseller': True,
                'variants': [
                    {'type': 'Wrist Length', 'name': '6.5 Inch (Small)', 'sku': 'MOD-BRC-004-65', 'price_adj': Decimal('-4000.00'), 'stock': 4},
                    {'type': 'Wrist Length', 'name': '7.0 Inch (Standard)', 'sku': 'MOD-BRC-004-70', 'price_adj': Decimal('0.00'), 'stock': 10},
                    {'type': 'Wrist Length', 'name': '7.5 Inch (Relaxed)', 'sku': 'MOD-BRC-004-75', 'price_adj': Decimal('5000.00'), 'stock': 5},
                ],
                'images': [
                    {'url': 'https://images.unsplash.com/photo-1598560917505-59a3ad559071?w=800&auto=format&fit=crop&q=80', 'alt': 'Elysian Diamond Tennis Bracelet', 'is_primary': True},
                    {'url': 'https://images.unsplash.com/photo-1611591475168-b39fae6bfbfe?w=800&auto=format&fit=crop&q=80', 'alt': 'Elysian Bracelet Detail', 'is_primary': False},
                ]
            },
            {
                'name': 'Lumière Diamond Solitaire Pendant',
                'slug': 'lumiere-diamond-solitaire-pendant',
                'sku': 'MOD-PND-005',
                'category': 'pendants',
                'collection': 'celestial-solitaires',
                'base_price': Decimal('38000.00'),
                'sale_price': Decimal('32999.00'),
                'metal_type': Product.MetalType.YELLOW_GOLD,
                'metal_purity': Product.MetalPurity.PURITY_18K,
                'gemstone': '0.50 ct Round Brilliant Diamond (F/VVS2)',
                'weight_grams': Decimal('2.90'),
                'short_description': 'A floating four-prong solitaire diamond pendant hung on a shimmering 18K gold cable chain.',
                'description': 'Effortlessly modern yet profoundly timeless, the Lumière Pendant highlights the diamond alone without distractions. Complete with an adjustable 16 to 18 inch delicate gold chain.',
                'is_featured': False,
                'is_new_arrival': True,
                'is_bestseller': False,
                'variants': [
                    {'type': 'Chain Metal', 'name': '18K Yellow Gold Chain', 'sku': 'MOD-PND-005-YG', 'price_adj': Decimal('0.00'), 'stock': 14},
                    {'type': 'Chain Metal', 'name': '18K Rose Gold Chain', 'sku': 'MOD-PND-005-RG', 'price_adj': Decimal('0.00'), 'stock': 8},
                ],
                'images': [
                    {'url': 'https://images.unsplash.com/photo-1602751584552-8ba73aad10e1?w=800&auto=format&fit=crop&q=80', 'alt': 'Lumière Diamond Solitaire Pendant', 'is_primary': True},
                ]
            },
            {
                'name': 'Gitanjali Antique Polki Temple Kada',
                'slug': 'gitanjali-antique-polki-kada',
                'sku': 'MOD-BRC-006',
                'category': 'bracelets',
                'collection': 'royal-heritage',
                'base_price': Decimal('195000.00'),
                'sale_price': Decimal('179000.00'),
                'metal_type': Product.MetalType.YELLOW_GOLD,
                'metal_purity': Product.MetalPurity.PURITY_22K,
                'gemstone': 'Natural Burmese Rubies & Uncut Polki',
                'weight_grams': Decimal('44.10'),
                'short_description': 'An artisan-crafted 22K antique gold openable kada featuring peacock motifs and ruby accents.',
                'description': 'Celebrating centuries-old nakashi temple jewellery techniques, the Gitanjali Kada is sculpted with floral relief carvings and studded with natural pigeon-blood rubies.',
                'is_featured': False,
                'is_new_arrival': False,
                'is_bestseller': True,
                'variants': [
                    {'type': 'Bangle Size', 'name': 'Size 2.4 (2.25 in diameter)', 'sku': 'MOD-BRC-006-24', 'price_adj': Decimal('0.00'), 'stock': 3},
                    {'type': 'Bangle Size', 'name': 'Size 2.6 (2.37 in diameter)', 'sku': 'MOD-BRC-006-26', 'price_adj': Decimal('0.00'), 'stock': 5},
                ],
                'images': [
                    {'url': 'https://images.unsplash.com/photo-1611591475168-b39fae6bfbfe?w=800&auto=format&fit=crop&q=80', 'alt': 'Gitanjali Antique Polki Kada', 'is_primary': True},
                ]
            }
        ]

        for p_data in products_data:
            cat = cat_objs[p_data['category']]
            col = col_objs.get(p_data['collection'])

            prod, created = Product.objects.update_or_create(
                slug=p_data['slug'],
                defaults={
                    'name': p_data['name'],
                    'sku': p_data['sku'],
                    'category': cat,
                    'collection': col,
                    'base_price': p_data['base_price'],
                    'sale_price': p_data['sale_price'],
                    'metal_type': p_data['metal_type'],
                    'metal_purity': p_data['metal_purity'],
                    'gemstone': p_data['gemstone'],
                    'weight_grams': p_data['weight_grams'],
                    'short_description': p_data['short_description'],
                    'description': p_data['description'],
                    'is_featured': p_data['is_featured'],
                    'is_new_arrival': p_data['is_new_arrival'],
                    'is_bestseller': p_data['is_bestseller'],
                    'is_active': True
                }
            )

            # Variants
            for v in p_data['variants']:
                ProductVariant.objects.update_or_create(
                    sku=v['sku'],
                    defaults={
                        'product': prod,
                        'variant_type': v['type'],
                        'variant_name': v['name'],
                        'price_adjustment': v['price_adj'],
                        'stock_quantity': v['stock'],
                        'is_active': True
                    }
                )

            # Images
            for idx, img_info in enumerate(p_data['images']):
                save_product_image(
                    prod,
                    img_info['url'],
                    img_info['alt'],
                    is_primary=img_info.get('is_primary', False),
                    display_order=idx
                )

        self.stdout.write(self.style.SUCCESS("[OK] Products, variants, and imagery seeded."))

        # 5. Coupons
        coupons_data = [
            {'code': 'WELCOME10', 'desc': '10% off for first-time jewellery patrons', 'type': Coupon.DiscountType.PERCENTAGE, 'val': Decimal('10.00'), 'min_order': Decimal('10000.00'), 'max_disc': Decimal('5000.00')},
            {'code': 'ROYAL15', 'desc': '15% off bridal suites and royal collections', 'type': Coupon.DiscountType.PERCENTAGE, 'val': Decimal('15.00'), 'min_order': Decimal('50000.00'), 'max_disc': Decimal('15000.00')},
            {'code': 'GLOW2000', 'desc': 'Flat ₹2,000 instant discount on orders above ₹25,000', 'type': Coupon.DiscountType.FIXED, 'val': Decimal('2000.00'), 'min_order': Decimal('25000.00'), 'max_disc': None},
        ]

        for c in coupons_data:
            Coupon.objects.update_or_create(
                code=c['code'],
                defaults={
                    'description': c['desc'],
                    'discount_type': c['type'],
                    'discount_value': c['val'],
                    'minimum_order_amount': c['min_order'],
                    'maximum_discount_amount': c['max_disc'],
                    'is_active': True
                }
            )
        self.stdout.write(self.style.SUCCESS("[OK] Coupons created (WELCOME10, ROYAL15, GLOW2000)."))

        # 6. Banners
        banners_data = [
            {
                'title': 'Timeless Radiance, Handcrafted in Gold & Diamonds',
                'subtitle': 'Discover certified solitaires and heirloom suites sculpted with precision and passion.',
                'cta_text': 'Explore The Collection',
                'cta_link': '/shop',
                'badge_text': 'Certified Natural Diamonds',
                'order': 1
            },
            {
                'title': 'The Royal Heritage Bridal Suite',
                'subtitle': 'Uncut polki and Colombian emeralds crafted for once-in-a-lifetime celebrations.',
                'cta_text': 'View Bridal Heirlooms',
                'cta_link': '/shop?collection=royal-heritage',
                'badge_text': 'Artisan Handcrafted',
                'order': 2
            }
        ]

        for b in banners_data:
            Banner.objects.update_or_create(
                title=b['title'],
                defaults={
                    'subtitle': b['subtitle'],
                    'cta_text': b['cta_text'],
                    'cta_link': b['cta_link'],
                    'badge_text': b['badge_text'],
                    'display_order': b['order'],
                    'is_active': True
                }
            )
        self.stdout.write(self.style.SUCCESS("[OK] Homepage promotional banners created."))

        # 7. Seed sample verified customer reviews
        admin_user = User.objects.filter(is_superuser=True).first()
        test_customer, _ = User.objects.get_or_create(
            email="priya.sharma@example.com",
            defaults={'role': User.Role.CUSTOMER, 'is_verified': True}
        )
        test_customer.set_password("CustomerPass2026!")
        test_customer.is_verified = True
        test_customer.save()
        if hasattr(test_customer, 'profile'):
            test_customer.profile.first_name = "Priya"
            test_customer.profile.last_name = "Sharma"
            test_customer.profile.save()

        aura_ring = Product.objects.filter(slug='aura-diamond-solitaire-ring').first()
        if aura_ring and test_customer:
            # Create a sample delivered order for Priya so she is an authentic verified purchaser
            order, o_created = Order.objects.get_or_create(
                order_number="MOD-SAMPLE-VERIFIED-01",
                defaults={
                    'user': test_customer,
                    'customer_email': test_customer.email,
                    'customer_phone': '+91 98200 12345',
                    'customer_name': 'Priya Sharma',
                    'shipping_full_name': 'Priya Sharma',
                    'shipping_phone': '+91 98200 12345',
                    'shipping_street': '14, Bandra Kurla Complex Road',
                    'shipping_city': 'Mumbai',
                    'shipping_state': 'Maharashtra',
                    'shipping_postal_code': '400051',
                    'status': Order.Status.DELIVERED,
                    'payment_status': Order.PaymentStatus.PAID_DEMO,
                    'subtotal_amount': Decimal('79999.00'),
                    'total_amount': Decimal('82398.97'),
                }
            )
            if o_created:
                OrderItem.objects.create(
                    order=order,
                    product=aura_ring,
                    product_name=aura_ring.name,
                    sku=aura_ring.sku,
                    unit_price=aura_ring.current_price,
                    quantity=1,
                    subtotal=aura_ring.current_price
                )

            # Create verified review
            Review.objects.update_or_create(
                product=aura_ring,
                user=test_customer,
                defaults={
                    'order': order,
                    'rating': 5,
                    'title': 'Absolutely breathtaking diamond fire and comfort',
                    'comment': 'The Aura Solitaire exceeded all my expectations! The diamond clarity is flawless, and the craftsmanship of the platinum prongs is exceptionally secure. Arrived in a gorgeous velvet luxury case with complete hallmarking certificates.',
                    'is_verified_purchase': True,
                    'moderation_status': Review.ModerationStatus.APPROVED
                }
            )
            self.stdout.write(self.style.SUCCESS("[OK] Seeded authentic verified purchaser review."))

        self.stdout.write(self.style.SUCCESS("[OK] Seeding completed successfully!"))
