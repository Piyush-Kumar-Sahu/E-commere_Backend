from rest_framework import serializers
from .models import Review, ReviewModerationLog
from apps.catalogue.models import Product
from apps.orders.models import Order, OrderItem

class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_slug = serializers.CharField(source='product.slug', read_only=True)

    class Meta:
        model = Review
        fields = (
            'id', 'product', 'product_name', 'product_slug', 'user_name',
            'rating', 'title', 'comment', 'is_verified_purchase',
            'moderation_status', 'created_at'
        )
        read_only_fields = ('id', 'is_verified_purchase', 'moderation_status', 'created_at')

    def get_user_name(self, obj):
        if hasattr(obj.user, 'profile') and obj.user.profile.display_name:
            name = obj.user.profile.display_name
            # Privacy masking: "Priya Sharma" -> "Priya S."
            parts = name.split()
            if len(parts) > 1:
                return f"{parts[0]} {parts[1][0]}."
            return name
        return obj.user.email.split('@')[0].capitalize()

class ReviewCreateSerializer(serializers.ModelSerializer):
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True), source='product', write_only=True
    )

    class Meta:
        model = Review
        fields = ('product_id', 'rating', 'title', 'comment')

    def validate(self, attrs):
        user = self.context['request'].user
        product = attrs['product']

        # Rule 1: Check if user already reviewed this product
        if Review.objects.filter(user=user, product=product).exists():
            raise serializers.ValidationError({
                "product": "You have already submitted a review for this jewellery piece."
            })

        # Rule 2: Server-side verification of purchase eligibility using Order records
        # Must have an order with this product that is confirmed, processing, shipped, or delivered
        eligible_order = Order.objects.filter(
            user=user,
            items__product=product,
            status__in=[
                Order.Status.CONFIRMED,
                Order.Status.PROCESSING,
                Order.Status.PACKED,
                Order.Status.SHIPPED,
                Order.Status.OUT_FOR_DELIVERY,
                Order.Status.DELIVERED
            ]
        ).first()

        if not eligible_order:
            raise serializers.ValidationError({
                "eligibility": "Only verified purchasers who have ordered this jewellery piece can submit a review."
            })

        self.context['eligible_order'] = eligible_order
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        eligible_order = self.context.get('eligible_order')
        return Review.objects.create(
            user=user,
            product=validated_data['product'],
            order=eligible_order,
            rating=validated_data['rating'],
            title=validated_data.get('title', ''),
            comment=validated_data['comment'],
            is_verified_purchase=True,
            moderation_status=Review.ModerationStatus.APPROVED
        )

class AdminReviewModerationSerializer(serializers.Serializer):
    moderation_status = serializers.ChoiceField(choices=Review.ModerationStatus.choices)
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)
