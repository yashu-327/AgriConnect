from django.contrib import admin
from .models import User, FarmerProfile, RestaurantProfile, Produce, Order, Rating, CounterOffer, DeliveryWindow, PriceForecast, SeasonalInfluence


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'role', 'first_name', 'last_name', 'trust_score', 'average_rating', 'is_active']
    list_filter = ['role', 'is_active', 'is_verified', 'verification_badge']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    readonly_fields = ['trust_score', 'total_transactions', 'successful_transactions', 'average_rating']


@admin.register(FarmerProfile)
class FarmerProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'farm_name', 'location']
    search_fields = ['user__username', 'farm_name', 'location']


@admin.register(RestaurantProfile)
class RestaurantProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'restaurant_name', 'restaurant_type']
    list_filter = ['restaurant_type']
    search_fields = ['restaurant_name']


@admin.register(Produce)
class ProduceAdmin(admin.ModelAdmin):
    list_display = ['name', 'farmer', 'quantity', 'price_per_kg', 'freshness_score', 'produce_state', 'status', 'expiry_date']
    list_filter = ['status', 'produce_state', 'freshness_grade', 'season', 'is_dynamic_priced', 'availability_date']
    search_fields = ['name', 'farmer__username']
    readonly_fields = ['created_at', 'updated_at', 'last_price_update', 'freshness_last_updated', 'produce_state']
    fieldsets = (
        ('Basic Info', {
            'fields': ('farmer', 'name', 'quantity', 'status', 'produce_state', 'contact_number')
        }),
        ('Pricing', {
            'fields': ('price_per_kg', 'base_price_per_kg', 'is_dynamic_priced', 'current_price_multiplier', 'last_price_update')
        }),
        ('Freshness & Quality', {
            'fields': ('freshness_score', 'freshness_grade', 'harvested_date', 'freshness_last_updated', 'quality_notes')
        }),
        ('Expiry & Spoilage', {
            'fields': ('shelf_life_days', 'expiry_date', 'storage_condition', 'spoilage_risk_percentage')
        }),
        ('Seasonal & Location', {
            'fields': ('season', 'growing_region', 'weather_dependent', 'optimal_weather_conditions')
        }),
        ('Forecasting', {
            'fields': ('estimated_yield_kg', 'demand_forecast_score', 'supply_competition')
        }),
        ('Availability', {
            'fields': ('availability_date', 'created_at', 'updated_at')
        }),
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'restaurant', 'farmer', 'produce', 'quantity_requested', 'total_price', 'status', 'negotiation_status']
    list_filter = ['status', 'negotiation_status', 'created_at', 'preferred_delivery_date']
    search_fields = ['restaurant__username', 'farmer__username', 'produce__name']
    readonly_fields = ['created_at', 'updated_at', 'total_price']
    fieldsets = (
        ('Order Details', {
            'fields': ('restaurant', 'farmer', 'produce', 'quantity_requested', 'total_price', 'status')
        }),
        ('Delivery', {
            'fields': ('preferred_delivery_date', 'preferred_delivery_time_start', 'preferred_delivery_time_end', 'delivery_address', 'delivery_notes', 'actual_delivery_date')
        }),
        ('Negotiation', {
            'fields': ('negotiation_status', 'original_unit_price', 'original_total_price', 'negotiation_notes')
        }),
        ('Quality Requirements', {
            'fields': ('minimum_freshness_required', 'quality_requirements')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ['id', 'from_user', 'to_user', 'score', 'rating_type', 'is_verified_purchase', 'created_at']
    list_filter = ['rating_type', 'score', 'is_verified_purchase', 'created_at']
    search_fields = ['from_user__username', 'to_user__username', 'comment']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(CounterOffer)
class CounterOfferAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'created_by', 'proposed_unit_price', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['order__id', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(DeliveryWindow)
class DeliveryWindowAdmin(admin.ModelAdmin):
    list_display = ['order', 'scheduled_date', 'time_slot_start', 'time_slot_end', 'delivery_confirmed']
    list_filter = ['scheduled_date', 'delivery_confirmed']
    search_fields = ['order__id']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(PriceForecast)
class PriceForecastAdmin(admin.ModelAdmin):
    list_display = ['produce', 'forecast_date', 'forecasted_price', 'confidence_score', 'forecast_accuracy']
    list_filter = ['forecast_date', 'confidence_score']
    search_fields = ['produce__name']
    readonly_fields = ['created_at']


@admin.register(SeasonalInfluence)
class SeasonalInfluenceAdmin(admin.ModelAdmin):
    list_display = ['produce', 'season', 'current_weather_score', 'risk_level', 'recorded_date']
    list_filter = ['season', 'risk_level', 'recorded_date']
    search_fields = ['produce__name', 'forecast_notes']
    readonly_fields = ['recorded_date', 'updated_date']
