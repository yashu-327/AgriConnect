from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ObjectDoesNotExist
from decimal import Decimal


class User(AbstractUser):
    """Custom User model with role-based authentication with trust scoring"""
    ROLE_CHOICES = [
        ('farmer', 'Farmer'),
        ('restaurant', 'Restaurant'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    phone = models.CharField(max_length=15, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Trust & Reputation Fields
    trust_score = models.FloatField(default=5.0, validators=[MinValueValidator(0.0), MaxValueValidator(10.0)])
    total_transactions = models.IntegerField(default=0)
    successful_transactions = models.IntegerField(default=0)
    average_rating = models.FloatField(default=5.0, validators=[MinValueValidator(0.0), MaxValueValidator(5.0)])
    
    # Verification Fields
    is_verified = models.BooleanField(default=False)
    verification_badge = models.BooleanField(default=False)  # Official badge
    
    class Meta:
        indexes = [
            models.Index(fields=['role', 'trust_score']),
        ]
    
    def is_farmer(self):
        return self.role == 'farmer'
    
    def is_restaurant(self):
        return self.role == 'restaurant'
    
    def update_trust_score(self):
        """Recalculate trust score based on transactions"""
        if self.total_transactions == 0:
            self.trust_score = 5.0
            return
        
        success_rate = (self.successful_transactions / self.total_transactions) * 10
        rating_weight = self.average_rating  # 0-5
        
        # Weighted average: 60% success rate, 40% ratings
        self.trust_score = (success_rate * 0.6) + (rating_weight * 0.8)
        self.trust_score = min(10.0, max(0.0, self.trust_score))
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    def get_farmer_location(self):
        """Return farmer location safely for templates."""
        try:
            return self.farmer_profile.location
        except ObjectDoesNotExist:
            return ''


class FarmerProfile(models.Model):
    """Extended profile for Farmers"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='farmer_profile')
    farm_name = models.CharField(max_length=200, blank=True)
    location = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.farm_name or self.user.username}'s Farm"


class RestaurantProfile(models.Model):
    """Extended profile for Restaurants"""
    RESTAURANT_TYPES = [
        ('fine-dining', 'Fine Dining'),
        ('casual', 'Casual Dining'),
        ('cafe', 'Cafe'),
        ('fast-food', 'Fast Food'),
        ('catering', 'Catering Service'),
        ('hotel', 'Hotel Restaurant'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='restaurant_profile')
    restaurant_name = models.CharField(max_length=200)
    restaurant_type = models.CharField(max_length=50, choices=RESTAURANT_TYPES)
    address = models.TextField()
    gst_number = models.CharField(max_length=20, blank=True)
    
    def __str__(self):
        return self.restaurant_name


class Produce(models.Model):
    """Produce listed by farmers with freshness, pricing, and seasonal tracking"""
    CATEGORY_CHOICES = [
        ('vegetables', 'Vegetables'),
        ('fruits', 'Fruits'),
        ('grains', 'Grains'),
        ('pulses', 'Pulses'),
        ('dairy', 'Dairy'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('available', 'Available'),
        ('pending', 'Pending'),
        ('sold', 'Sold Out'),
    ]
    
    # Production State Choices (based on freshness and expiry)
    PRODUCE_STATE_CHOICES = [
        ('fresh', 'Fresh'),
        ('aging', 'Aging'),
        ('near_expiry', 'Near Expiry'),
        ('expired', 'Expired'),
        ('unavailable', 'Unavailable'),
    ]
    
    FRESHNESS_CHOICES = [
        ('fresh', 'Fresh (Harvested Today)'),
        ('very_good', 'Very Good (1-2 days old)'),
        ('good', 'Good (3-5 days old)'),
        ('fair', 'Fair (6-10 days old)'),
        ('aged', 'Aged/Processed'),
    ]
    
    SEASON_CHOICES = [
        ('spring', 'Spring'),
        ('summer', 'Summer'),
        ('monsoon', 'Monsoon'),
        ('autumn', 'Autumn'),
        ('winter', 'Winter'),
        ('year_round', 'Year-Round'),
    ]
    
    STORAGE_TYPES = [
        ('ambient', 'Ambient Temperature'),
        ('cool', 'Cool Storage'),
        ('cold', 'Refrigerated'),
        ('frozen', 'Frozen'),
    ]
    
    # Original Fields
    farmer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='produce_listings')
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    crop_image = models.ImageField(upload_to='crop_images/', blank=True, null=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)  # in kg
    price_per_kg = models.DecimalField(max_digits=10, decimal_places=2)
    availability_date = models.DateField()
    contact_number = models.CharField(max_length=15, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    produce_state = models.CharField(max_length=20, choices=PRODUCE_STATE_CHOICES, default='fresh')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Freshness & Quality Fields
    freshness_score = models.FloatField(default=9.0, validators=[MinValueValidator(0.0), MaxValueValidator(10.0)])
    freshness_grade = models.CharField(max_length=20, choices=FRESHNESS_CHOICES, default='fresh')
    harvested_date = models.DateTimeField(null=True, blank=True)
    freshness_last_updated = models.DateTimeField(null=True, blank=True)
    quality_notes = models.TextField(blank=True, help_text="E.g., Organic, Pesticide-free, etc.")
    
    # Expiry & Spoilage Fields
    shelf_life_days = models.IntegerField(default=7, validators=[MinValueValidator(1)])
    expiry_date = models.DateField(null=True, blank=True)
    storage_condition = models.CharField(max_length=20, choices=STORAGE_TYPES, default='ambient')
    spoilage_risk_percentage = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(100.0)])
    
    # Dynamic Pricing Fields
    base_price_per_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    current_price_multiplier = models.FloatField(default=1.0, validators=[MinValueValidator(0.5), MaxValueValidator(3.0)])
    is_dynamic_priced = models.BooleanField(default=False)
    last_price_update = models.DateTimeField(null=True, blank=True)
    
    # Seasonal & Weather Influence Fields
    season = models.CharField(max_length=20, choices=SEASON_CHOICES, default='year_round')
    growing_region = models.CharField(max_length=200, blank=True)
    weather_dependent = models.BooleanField(default=False)
    optimal_weather_conditions = models.CharField(max_length=500, blank=True, help_text="Conditions that maximize yield")
    
    # Forecasting Metadata
    estimated_yield_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    demand_forecast_score = models.FloatField(default=5.0, validators=[MinValueValidator(0.0), MaxValueValidator(10.0)])
    supply_competition = models.IntegerField(default=0, help_text="Number of competitors selling same item")
    
    class Meta:
        verbose_name_plural = "Produce"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['farmer', 'status']),
            models.Index(fields=['expiry_date']),
            models.Index(fields=['freshness_score']),
            models.Index(fields=['demand_forecast_score']),
        ]
    
    def __str__(self):
        return f"{self.name} by {self.farmer.username}"
    
    def update_status(self):
        """Auto-update status based on quantity and expiry (legacy, kept for compatibility)"""
        if self.quantity <= 0:
            self.status = 'sold'
        elif self.expiry_date and self.expiry_date <= timezone.now().date():
            self.status = 'sold'  # Expired
        elif self.quantity < 50:
            self.status = 'pending'  # Low stock
        else:
            self.status = 'available'
        self.save()
    
    def calculate_freshness_decay(self):
        """
        Calculate current freshness score based on time since harvest.
        Returns updated freshness_score (0-10).
        Decay accelerates as produce ages.
        """
        if not self.harvested_date:
            return self.freshness_score
        
        hours_since_harvest = (timezone.now() - self.harvested_date).total_seconds() / 3600
        days_since_harvest = hours_since_harvest / 24
        shelf_life = self.shelf_life_days
        
        # Decay model: starts slow, accelerates toward end
        # Uses exponential decay: freshness = 10 * e^(-0.1 * days/shelf_life)
        import math
        decay_rate = 0.1
        normalized_age = (days_since_harvest / shelf_life) if shelf_life > 0 else 0
        decayed_score = 10.0 * math.exp(-decay_rate * normalized_age)
        
        # Cap at 0-10 range
        return max(0.0, min(10.0, decayed_score))
    
    def calculate_spoilage_risk(self):
        """
        Calculate spoilage risk percentage (0-100).
        Risk accelerates dramatically in final days.
        """
        days_left = self.days_until_expiry()
        if days_left is None or days_left < 0:
            return 100.0  # Already expired
        
        if days_left <= 0:
            return 100.0
        elif days_left <= 1:
            return 90.0
        elif days_left <= 2:
            return 70.0
        elif days_left <= 3:
            return 50.0
        elif days_left <= 5:
            return 25.0
        else:
            # Baseline risk for stable storage
            return 5.0
    
    def get_produce_state(self):
        """
        Determine current produce state based on freshness and expiry.
        Returns one of: fresh, aging, near_expiry, expired, unavailable
        """
        # Check if expired
        if self.expiry_date and self.expiry_date <= timezone.now().date():
            return 'expired'
        
        # Check if quantity is 0 (sold out)
        if self.quantity <= 0:
            return 'unavailable'
        
        # Based on days until expiry
        days_left = self.days_until_expiry()
        if days_left is None:
            return 'aging'  # No expiry set, assume aging
        
        if days_left <= 2:
            return 'near_expiry'
        elif days_left <= 5:
            return 'aging'
        else:
            return 'fresh'
    
    def calculate_expiry_date(self):
        """Calculate expiry date based on harvest date and shelf life"""
        if self.harvested_date:
            return self.harvested_date.date() + timezone.timedelta(days=self.shelf_life_days)
        return None
    
    def days_until_expiry(self):
        """Get days remaining before expiry"""
        if self.expiry_date:
            delta = self.expiry_date - timezone.now().date()
            return delta.days
        return None
    
    def update_dynamic_price(self):
        """Update price based on demand, freshness, and time to expiry"""
        if not self.is_dynamic_priced or not self.base_price_per_kg:
            self.price_per_kg = self.base_price_per_kg or self.price_per_kg
            return
        
        multiplier = self.current_price_multiplier
        
        # Demand-based adjustment (demand forecast score influences price)
        demand_factor = 0.8 + (self.demand_forecast_score / 10.0) * 0.4  # 0.8 to 1.2
        
        # Freshness-based adjustment
        freshness_factor = 0.7 + (self.freshness_score / 10.0) * 0.6  # 0.7 to 1.3
        
        # Days to expiry adjustment (reduce price as expiry approaches)
        days_left = self.days_until_expiry() or self.shelf_life_days
        if days_left <= 2:
            expiry_factor = 0.5  # 50% discount if expiring soon
        elif days_left <= 5:
            expiry_factor = 0.75  # 25% discount
        else:
            expiry_factor = 1.0
        
        # Calculate final price
        calculated_price = self.base_price_per_kg * demand_factor * freshness_factor * expiry_factor
        self.price_per_kg = calculated_price
        self.last_price_update = timezone.now()
    
    def refresh_freshness_and_state(self):
        """
        Recalculate freshness score, spoilage risk, and produce state.
        Call this periodically or when accessing produce details.
        """
        # Update freshness score based on decay
        self.freshness_score = self.calculate_freshness_decay()
        
        # Update spoilage risk
        self.spoilage_risk_percentage = self.calculate_spoilage_risk()
        
        # Update produce state
        self.produce_state = self.get_produce_state()
        
        # Update freshness grade based on score
        if self.freshness_score >= 9.0:
            self.freshness_grade = 'fresh'
        elif self.freshness_score >= 7.0:
            self.freshness_grade = 'very_good'
        elif self.freshness_score >= 5.0:
            self.freshness_grade = 'good'
        elif self.freshness_score >= 2.0:
            self.freshness_grade = 'fair'
        else:
            self.freshness_grade = 'aged'
        
        self.freshness_last_updated = timezone.now()
    
    def save(self, *args, **kwargs):
        # Calculate expiry date if not set
        if not self.expiry_date and self.harvested_date:
            self.expiry_date = self.calculate_expiry_date()
        
        # Update dynamic price if enabled
        if self.is_dynamic_priced:
            self.update_dynamic_price()
        
        super().save(*args, **kwargs)


class Order(models.Model):
    """Orders/Requests from restaurants to farmers with delivery and negotiation support"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    NEGOTIATION_STATUS = [
        ('no_offer', 'No Counter Offer'),
        ('counter_pending', 'Counter Offer Pending'),
        ('counter_accepted', 'Counter Offer Accepted'),
        ('counter_rejected', 'Counter Offer Rejected'),
    ]
    
    # Original Fields
    restaurant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    farmer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_orders')
    produce = models.ForeignKey(Produce, on_delete=models.CASCADE, related_name='orders')
    quantity_requested = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Delivery Window Fields
    preferred_delivery_date = models.DateField(null=True, blank=True)
    preferred_delivery_time_start = models.TimeField(null=True, blank=True, help_text="HH:MM format")
    preferred_delivery_time_end = models.TimeField(null=True, blank=True)
    delivery_address = models.TextField(blank=True)
    delivery_notes = models.TextField(blank=True)
    actual_delivery_date = models.DateTimeField(null=True, blank=True)
    
    # Negotiation Fields
    negotiation_status = models.CharField(max_length=20, choices=NEGOTIATION_STATUS, default='no_offer')
    original_unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    original_total_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    negotiation_notes = models.TextField(blank=True)
    
    # Quality & Freshness Requirements
    minimum_freshness_required = models.CharField(max_length=20, choices=Produce.FRESHNESS_CHOICES, default='very_good')
    quality_requirements = models.TextField(blank=True, help_text="Specific quality standards")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['restaurant', 'status']),
            models.Index(fields=['farmer', 'status']),
            models.Index(fields=['preferred_delivery_date']),
        ]
    
    def __str__(self):
        return f"Order #{self.id} - {self.produce.name}"
    
    def save(self, *args, **kwargs):
        # Calculate total price
        self.total_price = self.quantity_requested * self.produce.price_per_kg
        super().save(*args, **kwargs)


class Rating(models.Model):
    """Ratings and reviews for farmers and restaurants"""
    RATING_TYPES = [
        ('farmer', 'Farmer Rating'),
        ('restaurant', 'Restaurant Rating'),
    ]
    
    rating_type = models.CharField(max_length=20, choices=RATING_TYPES)
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings_given')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings_received')
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='ratings', null=True, blank=True)
    
    # Rating Fields
    score = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    
    # Specific Criteria (for detailed feedback)
    quality_score = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True)
    timeliness_score = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True)
    communication_score = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True)
    
    is_verified_purchase = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('from_user', 'to_user', 'order')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['to_user', 'score']),
            models.Index(fields=['rating_type', 'score']),
        ]
    
    def __str__(self):
        return f"Rating: {self.from_user.username} → {self.to_user.username} ({self.score}★)"


class CounterOffer(models.Model):
    """Counter-offer/negotiation records for orders"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ]
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='counter_offers')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='counter_offers_created')
    
    # Counter Offer Details
    proposed_quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    proposed_unit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    proposed_total_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    proposed_delivery_date = models.DateField(null=True, blank=True)
    
    reasoning = models.TextField(blank=True, help_text="Why this counter-offer was made")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    expires_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order', 'status']),
            models.Index(fields=['created_by', 'status']),
        ]
    
    def __str__(self):
        return f"Counter Offer for Order #{self.order.id} - {self.status}"
    
    def is_expired(self):
        """Check if counter-offer has expired"""
        if self.expires_at and self.expires_at <= timezone.now():
            return True
        return False


class DeliveryWindow(models.Model):
    """Available delivery slots/windows for supply"""
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery_window')
    
    scheduled_date = models.DateField()
    time_slot_start = models.TimeField()
    time_slot_end = models.TimeField()
    
    delivery_location = models.CharField(max_length=300, blank=True)
    special_instructions = models.TextField(blank=True)
    
    estimated_arrival = models.DateTimeField(null=True, blank=True)
    actual_arrival = models.DateTimeField(null=True, blank=True)
    delivery_confirmed = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['scheduled_date', 'time_slot_start']
    
    def __str__(self):
        return f"Delivery for Order #{self.order.id} on {self.scheduled_date}"


class PriceForecast(models.Model):
    """Price forecasting data for produce"""
    produce = models.ForeignKey(Produce, on_delete=models.CASCADE, related_name='price_forecasts')
    
    forecast_date = models.DateField()
    forecasted_price = models.DecimalField(max_digits=10, decimal_places=2)
    confidence_score = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    
    factors = models.JSONField(default=dict, blank=True, help_text="JSON dict of price influencing factors")
    # Example: {"demand": 8, "supply": 3, "seasonality": 0.9, "weather": 1.1}
    
    actual_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    forecast_accuracy = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['produce', '-forecast_date']
        unique_together = ('produce', 'forecast_date')
        indexes = [
            models.Index(fields=['produce', 'forecast_date']),
            models.Index(fields=['forecast_date']),
        ]
    
    def __str__(self):
        return f"Price forecast for {self.produce.name} on {self.forecast_date}"


class SeasonalInfluence(models.Model):
    """Weather and seasonal influence tracking on produce"""
    produce = models.ForeignKey(Produce, on_delete=models.CASCADE, related_name='seasonal_influences')
    
    # Seasonal Data
    season = models.CharField(max_length=50, choices=Produce.SEASON_CHOICES)
    historical_yield_multiplier = models.FloatField(default=1.0, help_text="1.0 = normal, >1.0 = higher yield")
    price_multiplier = models.FloatField(default=1.0, help_text="Seasonal price adjustment")
    
    # Weather Influence
    optimal_temperature_min = models.FloatField(null=True, blank=True, help_text="Celsius")
    optimal_temperature_max = models.FloatField(null=True, blank=True)
    optimal_rainfall_mm = models.FloatField(null=True, blank=True, help_text="MM per month")
    
    current_weather_score = models.FloatField(default=5.0, validators=[MinValueValidator(0.0), MaxValueValidator(10.0)])
    growth_stage = models.CharField(max_length=100, blank=True, help_text="E.g., Germination, Vegetative, Flowering, Harvesting")
    
    # Impact Metrics
    quality_impact = models.FloatField(default=1.0, help_text="1.0 = no impact, >1.0 = positive, <1.0 = negative")
    yield_impact = models.FloatField(default=1.0)
    risk_level = models.CharField(
        max_length=20,
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')],
        default='low'
    )
    
    forecast_notes = models.TextField(blank=True)
    
    recorded_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_date']
        verbose_name_plural = "Seasonal Influences"
        indexes = [
            models.Index(fields=['produce', 'season']),
            models.Index(fields=['recorded_date']),
        ]
    
    def __str__(self):
        return f"Seasonal influence for {self.produce.name} ({self.season})"
