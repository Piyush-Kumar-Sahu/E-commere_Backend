from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Collection(models.Model):
    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    tagline = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    banner_image = models.ImageField(upload_to='collections/', blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Product(models.Model):
    class MetalType(models.TextChoices):
        YELLOW_GOLD = 'yellow_gold', _('Yellow Gold')
        ROSE_GOLD = 'rose_gold', _('Rose Gold')
        WHITE_GOLD = 'white_gold', _('White Gold')
        PLATINUM = 'platinum', _('Platinum')
        STERLING_SILVER = 'sterling_silver', _('925 Sterling Silver')
        BRASS_ALLOY = 'brass_alloy', _('Gold Plated Brass')

    class MetalPurity(models.TextChoices):
        PURITY_24K = '24k', _('24 Karat (99.9%)')
        PURITY_22K = '22k', _('22 Karat (91.6%)')
        PURITY_18K = '18k', _('18 Karat (75.0%)')
        PURITY_14K = '14k', _('14 Karat (58.5%)')
        SILVER_925 = '925', _('925 Sterling Silver')
        FASHION = 'fashion', _('Fashion Jewellery')

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    collection = models.ForeignKey(Collection, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    sku = models.CharField(max_length=60, unique=True)
    short_description = models.CharField(max_length=300, blank=True)
    description = models.TextField()

    # Pricing
    base_price = models.DecimalField(max_digits=12, decimal_places=2)
    sale_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Jewellery Specifications
    metal_type = models.CharField(max_length=30, choices=MetalType.choices, default=MetalType.YELLOW_GOLD)
    metal_purity = models.CharField(max_length=20, choices=MetalPurity.choices, default=MetalPurity.PURITY_18K)
    gemstone = models.CharField(max_length=100, default='Natural Diamond', blank=True)
    weight_grams = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    dimensions = models.CharField(max_length=150, blank=True, help_text="e.g. 18mm x 12mm")
    packaging_info = models.CharField(max_length=200, default="Luxury velvet case with authenticity certificate")
    care_instructions = models.TextField(blank=True, default="Store in an airtight pouch. Avoid contact with perfumes, moisture, and chemical cleaners. Wipe gently with a soft microfibre cloth.")

    # Merchandising flags
    is_featured = models.BooleanField(default=False)
    is_new_arrival = models.BooleanField(default=False)
    is_bestseller = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.sku})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            candidate = base_slug
            idx = 1
            while Product.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base_slug}-{idx}"
                idx += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    @property
    def current_price(self):
        return self.sale_price if self.sale_price and self.sale_price > 0 else self.base_price

    @property
    def primary_image_url(self):
        primary = self.images.filter(is_primary=True).first()
        if not primary:
            primary = self.images.first()
        if primary and primary.image:
            return primary.image.url
        return None

    @property
    def total_stock(self):
        variants = self.variants.filter(is_active=True)
        if variants.exists():
            return sum(v.stock_quantity for v in variants)
        return 0

    @property
    def is_in_stock(self):
        return self.total_stock > 0

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', '-is_primary', 'id']

    def __str__(self):
        return f"Image for {self.product.name} (#{self.id})"

    def save(self, *args, **kwargs):
        if self.is_primary:
            ProductImage.objects.filter(product=self.product, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)

class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    variant_type = models.CharField(max_length=50, help_text="e.g. Ring Size, Chain Length, Metal Color")
    variant_name = models.CharField(max_length=100, help_text="e.g. Size 7, 18-Inch Chain, Rose Gold")
    sku = models.CharField(max_length=80, unique=True)
    price_adjustment = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Added to product current price")
    stock_quantity = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.product.name} - {self.variant_name} ({self.stock_quantity} in stock)"

    @property
    def final_price(self):
        return self.product.current_price + self.price_adjustment

    @property
    def is_in_stock(self):
        return self.stock_quantity > 0 and self.is_active
