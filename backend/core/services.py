"""
Produce Management Service Layer
Handles freshness decay, expiry management, dynamic pricing, stock state updates,
recommendations, and demand forecasting.
"""

from django.utils import timezone
from django.db.models import Q, Avg, Sum, Count
from decimal import Decimal
import math
from .models import Produce, Order, Rating, User


class ProduceStateManager:
    """
    Service class for managing produce lifecycle states.
    Provides deterministic, reusable methods for:
    - Freshness decay calculations
    - Spoilage risk assessment
    - Produce state transitions
    - Dynamic price updates
    - Batch state updates
    """
    
    # Constants for freshness decay
    BASE_FRESHNESS = 10.0
    DECAY_RATE = 0.1  # Controls how fast freshness decreases
    
    # Constants for spoilage risk
    SPOILAGE_THRESHOLDS = {
        0: 100.0,   # Expired or sold
        1: 90.0,    # 1 day left
        2: 70.0,    # 2 days left
        3: 50.0,    # 3 days left
        5: 25.0,    # 5 days left
        # Beyond 5 days: 5% baseline
    }
    
    @staticmethod
    def calculate_freshness_score(produce):
        """
        Calculate current freshness score using exponential decay model.
        
        Args:
            produce (Produce): Produce instance
        
        Returns:
            float: Freshness score 0-10
        """
        if not produce.harvested_date:
            return produce.freshness_score  # Return existing if no harvest date
        
        hours_since_harvest = (timezone.now() - produce.harvested_date).total_seconds() / 3600
        days_since_harvest = hours_since_harvest / 24
        shelf_life = produce.shelf_life_days
        
        if shelf_life <= 0:
            return 0.0
        
        # Exponential decay model
        normalized_age = days_since_harvest / shelf_life
        decayed_score = ProduceStateManager.BASE_FRESHNESS * math.exp(
            -ProduceStateManager.DECAY_RATE * normalized_age
        )
        
        return max(0.0, min(ProduceStateManager.BASE_FRESHNESS, decayed_score))
    
    @staticmethod
    def calculate_spoilage_risk(produce):
        """
        Calculate spoilage risk percentage based on time to expiry.
        Risk accelerates exponentially as expiry approaches.
        
        Args:
            produce (Produce): Produce instance
        
        Returns:
            float: Spoilage risk 0-100%
        """
        days_left = produce.days_until_expiry()
        
        if days_left is None or days_left < 0:
            return 100.0  # Already expired
        
        # Use predefined thresholds for exact match, otherwise interpolate
        for threshold_days, risk_pct in sorted(
            ProduceStateManager.SPOILAGE_THRESHOLDS.items()
        ):
            if days_left <= threshold_days:
                return risk_pct
        
        # Baseline risk for stable storage (> 5 days)
        return 5.0
    
    @staticmethod
    def get_produce_state(produce):
        """
        Determine produce state: fresh, aging, near_expiry, expired, or unavailable.
        
        Args:
            produce (Produce): Produce instance
        
        Returns:
            str: State choice (fresh, aging, near_expiry, expired, unavailable)
        """
        # Check if expired first
        if produce.expiry_date and produce.expiry_date <= timezone.now().date():
            return 'expired'
        
        # Check if sold out (unavailable)
        if produce.quantity <= 0:
            return 'unavailable'
        
        # Determine state based on days until expiry
        days_left = produce.days_until_expiry()
        
        if days_left is None:
            return 'aging'  # No expiry set, assume aging state
        
        if days_left <= 2:
            return 'near_expiry'
        elif days_left <= 5:
            return 'aging'
        else:
            return 'fresh'
    
    @staticmethod
    def calculate_Grade_from_score(freshness_score):
        """
        Map freshness score (0-10) to grade choice.
        
        Args:
            freshness_score (float): Score 0-10
        
        Returns:
            str: Grade choice (fresh, very_good, good, fair, aged)
        """
        if freshness_score >= 9.0:
            return 'fresh'
        elif freshness_score >= 7.0:
            return 'very_good'
        elif freshness_score >= 5.0:
            return 'good'
        elif freshness_score >= 2.0:
            return 'fair'
        else:
            return 'aged'
    
    @staticmethod
    def refresh_produce_state(produce, save=False):
        """
        Fully refresh produce freshness, spoilage, state, and grade.
        
        Args:
            produce (Produce): Produce instance to update
            save (bool): Whether to save to database
        
        Returns:
            Produce: Updated produce instance
        """
        # Calculate all freshness metrics
        produce.freshness_score = ProduceStateManager.calculate_freshness_score(produce)
        produce.spoilage_risk_percentage = ProduceStateManager.calculate_spoilage_risk(produce)
        produce.produce_state = ProduceStateManager.get_produce_state(produce)
        produce.freshness_grade = ProduceStateManager.calculate_Grade_from_score(
            produce.freshness_score
        )
        produce.freshness_last_updated = timezone.now()
        
        if save:
            produce.save()
        
        return produce
    
    @staticmethod
    def calculate_dynamic_price(produce):
        """
        Calculate dynamic price based on freshness, demand, and expiry.
        
        Args:
            produce (Produce): Produce instance
        
        Returns:
            Decimal: Calculated price per kg, or original if not dynamic
        """
        if not produce.is_dynamic_priced or not produce.base_price_per_kg:
            return produce.base_price_per_kg or produce.price_per_kg
        
        # Demand factor: 0.8 to 1.2 (from demand forecast score 0-10)
        demand_factor = 0.8 + (produce.demand_forecast_score / 10.0) * 0.4
        
        # Freshness factor: 0.7 to 1.3 (from freshness score 0-10)
        freshness_factor = 0.7 + (produce.freshness_score / 10.0) * 0.6
        
        # Expiry factor: 0.5 to 1.0 (discount as expiry approaches)
        days_left = produce.days_until_expiry()
        if days_left is None:
            expiry_factor = 1.0
        elif days_left <= 2:
            expiry_factor = 0.5  # 50% discount
        elif days_left <= 5:
            expiry_factor = 0.75  # 25% discount
        else:
            expiry_factor = 1.0
        
        # Calculate final price
        calculated_price = (
            produce.base_price_per_kg * demand_factor * freshness_factor * expiry_factor
        )
        
        return calculated_price
    
    @staticmethod
    def update_produce_price(produce, save=False):
        """
        Update produce price if dynamic pricing is enabled.
        
        Args:
            produce (Produce): Produce instance
            save (bool): Whether to save to database
        
        Returns:
            Decimal: Updated price
        """
        if produce.is_dynamic_priced:
            produce.price_per_kg = ProduceStateManager.calculate_dynamic_price(produce)
            produce.last_price_update = timezone.now()
            
            if save:
                produce.save()
        
        return produce.price_per_kg
    
    @staticmethod
    def batch_update_produce_states(produce_queryset=None, limit=None):
        """
        Batch update all produce items' states and freshness.
        Use this in a periodic task (e.g., daily cron job).
        
        Args:
            produce_queryset (QuerySet): Optional custom queryset. Defaults to all.
            limit (int): Maximum number to update. None = all.
        
        Returns:
            dict: Statistics of update operation
        """
        if produce_queryset is None:
            produce_queryset = Produce.objects.all()
        
        if limit:
            produce_queryset = produce_queryset[:limit]
        
        produced_queryset = produce_queryset.select_for_update()
        
        updated_count = 0
        expired_count = 0
        price_updated_count = 0
        
        for produce in produce_queryset:
            old_state = produce.produce_state
            
            # Refresh all metrics
            ProduceStateManager.refresh_produce_state(produce, save=False)
            
            # Update dynamic price if applicable
            if produce.is_dynamic_priced:
                ProduceStateManager.update_produce_price(produce, save=False)
                price_updated_count += 1
            
            # Track if produce moved to expired state
            if old_state != 'expired' and produce.produce_state == 'expired':
                expired_count += 1
            
            # Save updates
            produce.save()
            updated_count += 1
        
        return {
            'updated_count': updated_count,
            'expired_count': expired_count,
            'price_updated_count': price_updated_count,
        }


class DynamicPricingCalculator:
    """
    Helper class for advanced dynamic pricing calculations.
    Supports multi-factor pricing scenarios.
    """
    
    @staticmethod
    def apply_demand_multiplier(base_price, demand_score, intensity=1.0):
        """
        Apply demand-based price multiplier.
        
        Args:
            base_price (Decimal): Base price
            demand_score (float): Demand forecast score (0-10)
            intensity (float): Multiplier intensity for sensitivity (default 1.0)
        
        Returns:
            Decimal: Adjusted price
        """
        factor = 0.8 + (demand_score / 10.0) * 0.4 * intensity
        return Decimal(str(base_price)) * Decimal(str(factor))
    
    @staticmethod
    def apply_freshness_discount(base_price, freshness_score, intensity=1.0):
        """
        Apply freshness-based discount/premium.
        
        Args:
            base_price (Decimal): Base price
            freshness_score (float): Freshness score (0-10)
            intensity (float): Multiplier intensity (default 1.0)
        
        Returns:
            Decimal: Adjusted price
        """
        factor = 0.7 + (freshness_score / 10.0) * 0.6 * intensity
        return Decimal(str(base_price)) * Decimal(str(factor))
    
    @staticmethod
    def apply_expiry_discount(base_price, days_until_expiry):
        """
        Apply automatic expiry-based discount (clearance pricing).
        
        Args:
            base_price (Decimal): Base price
            days_until_expiry (int): Days before expiry
        
        Returns:
            Decimal: Discounted price
        """
        if days_until_expiry is None or days_until_expiry < 0:
            factor = 0.1  # 90% discount if expired
        elif days_until_expiry <= 1:
            factor = 0.3  # 70% discount
        elif days_until_expiry <= 2:
            factor = 0.5  # 50% discount
        elif days_until_expiry <= 5:
            factor = 0.75  # 25% discount
        else:
            factor = 1.0  # No discount
        
        return Decimal(str(base_price)) * Decimal(str(factor))
    
    @staticmethod
    def calculate_bulk_discount(quantity, bulk_thresholds):
        """
        Calculate bulk purchase discount multiplier.
        
        Args:
            quantity (Decimal): Order quantity
            bulk_thresholds (dict): Example: {100: 0.9, 500: 0.8, 1000: 0.7}
                                   (at 100kg, apply 10% discount)
        
        Returns:
            float: Multiplier to apply to price
        """
        multiplier = 1.0
        for threshold_qty, discount_factor in sorted(bulk_thresholds.items()):
            if quantity >= threshold_qty:
                multiplier = discount_factor
        
        return multiplier


class StockStateManager:
    """
    Helper class for managing stock states and transitions.
    """
    
    @staticmethod
    def should_mark_unavailable(produce):
        """
        Check if produce should be marked unavailable.
        
        Args:
            produce (Produce): Produce instance
        
        Returns:
            bool: True if should be unavailable
        """
        # Expired
        if produce.expiry_date and produce.expiry_date <= timezone.now().date():
            return True
        
        # Sold out
        if produce.quantity <= 0:
            return True
        
        # High spoilage risk
        if produce.spoilage_risk_percentage >= 95:
            return True
        
        return False
    
    @staticmethod
    def auto_reduce_quantity_on_order_accepted(produce, quantity_sold):
        """
        Auto-reduce produce quantity when order is accepted.
        
        Args:
            produce (Produce): Produce instance
            quantity_sold (Decimal): Amount sold
        
        Returns:
            Produce: Updated produce instance
        """
        produce.quantity -= quantity_sold
        produce.quantity = max(Decimal('0'), produce.quantity)  # Don't go negative
        
        # Auto-update state after quantity change
        new_state = ProduceStateManager.get_produce_state(produce)
        produce.produce_state = new_state
        
        return produce
    
    @staticmethod
    def get_available_stock_info(produce):
        """
        Get detailed stock information.
        
        Args:
            produce (Produce): Produce instance
        
        Returns:
            dict: Stock info with availability status and metrics
        """
        return {
            'quantity': float(produce.quantity),
            'state': produce.produce_state,
            'is_available': produce.produce_state not in ['expired', 'unavailable'],
            'freshness_score': round(produce.freshness_score, 2),
            'spoilage_risk': round(produce.spoilage_risk_percentage, 1),
            'days_until_expiry': produce.days_until_expiry(),
            'price_per_kg': float(produce.price_per_kg),
            'last_updated': produce.freshness_last_updated,
        }


class TrustScoreService:
    """
    Service class for managing trust scores and ratings.
    Calculates trust scores based on order history, ratings, and user behavior.
    """
    
    MIN_TRUST_SCORE = 0.0
    MAX_TRUST_SCORE = 100.0
    
    @staticmethod
    def calculate_trust_score(user):
        """
        Calculate trust score for a user based on order history and ratings.
        
        Args:
            user (User): User instance (Farmer or Buyer)
        
        Returns:
            float: Trust score 0-100
        """
        if not user:
            return TrustScoreService.MIN_TRUST_SCORE
        
        # Get completed orders for this user
        completed_orders = Order.objects.filter(
            Q(farmer=user) | Q(buyer=user),
            status='completed'
        ).count()
        
        # Get average rating for this user
        ratings = Rating.objects.filter(
            Q(rated_farmer=user) | Q(rated_buyer=user)
        )
        
        avg_rating = ratings.aggregate(Avg('rating'))['rating__avg'] or 0.0
        
        # Get total ratings count
        rating_count = ratings.count()
        
        # Calculate trust score components
        # Orders component: max 40 points (1 point per 5 completed orders, capped)
        orders_score = min(40.0, completed_orders / 5.0 * 10.0)
        
        # Rating component: max 50 points (rated out of 5, converted to 0-50)
        rating_score = (avg_rating / 5.0) * 50.0 if avg_rating > 0 else 0.0
        
        # Rating frequency component: max 10 points (minimum 5 ratings for bonus)
        frequency_score = min(10.0, max(0.0, (rating_count - 5) / 5.0 * 10.0))
        
        # Combine components
        trust_score = orders_score + rating_score + frequency_score
        
        # Clamp to valid range
        return max(
            TrustScoreService.MIN_TRUST_SCORE,
            min(TrustScoreService.MAX_TRUST_SCORE, trust_score)
        )
    
    @staticmethod
    def update_user_trust_score(user, save=True):
        """
        Update a user's trust score in the database.
        
        Args:
            user (User): User instance
            save (bool): Whether to save to database
        
        Returns:
            User: Updated user instance with new trust score
        """
        user.trust_score = TrustScoreService.calculate_trust_score(user)
        
        if save:
            user.save()
        
        return user
    
    @staticmethod
    def get_user_trust_level(trust_score):
        """
        Classify trust score into levels.
        
        Args:
            trust_score (float): Trust score 0-100
        
        Returns:
            str: Trust level (very_low, low, medium, high, very_high)
        """
        if trust_score >= 85.0:
            return 'very_high'
        elif trust_score >= 70.0:
            return 'high'
        elif trust_score >= 50.0:
            return 'medium'
        elif trust_score >= 25.0:
            return 'low'
        else:
            return 'very_low'


class OrderCompletionService:
    """
    Service class for managing order completion and related actions.
    Handles order status updates, completion validation, and post-completion tasks.
    """
    
    @staticmethod
    def can_complete_order(order):
        """
        Check if an order can be marked as completed.
        
        Args:
            order (Order): Order instance
        
        Returns:
            tuple: (can_complete: bool, reason: str)
        """
        if not order:
            return False, "Order does not exist"
        
        # Check if order is in acceptable state for completion
        if order.status not in ['accepted', 'in_transit', 'delivered']:
            return False, f"Order cannot be completed from '{order.status}' status"
        
        # Check if produce is still available (not expired or sold out)
        if order.produce and order.produce.produce_state == 'expired':
            return False, "Produce has expired"
        
        # Additional validation: buyer and farmer exist
        if not order.buyer or not order.farmer:
            return False, "Order missing buyer or farmer information"
        
        return True, "Order can be completed"
    
    @staticmethod
    def complete_order(order, save=True):
        """
        Mark an order as completed and perform related actions.
        
        Args:
            order (Order): Order instance
            save (bool): Whether to save to database
        
        Returns:
            tuple: (success: bool, order: Order, message: str)
        """
        can_complete, reason = OrderCompletionService.can_complete_order(order)
        
        if not can_complete:
            return False, order, reason
        
        try:
            # Update order status
            order.status = 'completed'
            order.completed_at = timezone.now()
            
            # Update user trust scores
            TrustScoreService.update_user_trust_score(order.buyer, save=False)
            TrustScoreService.update_user_trust_score(order.farmer, save=False)
            
            # Save order
            if save:
                order.save()
                order.buyer.save()
                order.farmer.save()
            
            return True, order, "Order completed successfully"
        
        except Exception as e:
            return False, order, f"Error completing order: {str(e)}"
    
    @staticmethod
    def get_order_completion_time(order):
        """
        Calculate the time taken to complete an order.
        
        Args:
            order (Order): Completed order instance
        
        Returns:
            dict: Time information
        """
        if order.status != 'completed' or not order.completed_at or not order.created_at:
            return {
                'is_completed': False,
                'completion_time_hours': None,
                'completion_time_days': None,
            }
        
        time_diff = order.completed_at - order.created_at
        hours = time_diff.total_seconds() / 3600
        days = time_diff.days
        
        return {
            'is_completed': True,
            'completion_time_hours': round(hours, 2),
            'completion_time_days': days,
        }
    
    @staticmethod
    def batch_complete_orders(order_queryset=None, filter_criteria=None):
        """
        Batch complete multiple orders meeting certain criteria.
        Useful for scheduled tasks or bulk operations.
        
        Args:
            order_queryset (QuerySet): Optional custom queryset. Defaults to all.
            filter_criteria (dict): Additional filters (e.g., {'status': 'delivered'})
        
        Returns:
            dict: Statistics of completion operation
        """
        if order_queryset is None:
            order_queryset = Order.objects.all()
        
        if filter_criteria:
            order_queryset = order_queryset.filter(**filter_criteria)
        
        # Default: only orders in deliverable states
        order_queryset = order_queryset.filter(status__in=['accepted', 'in_transit', 'delivered'])
        
        completed_count = 0
        failed_count = 0
        errors = []
        
        for order in order_queryset.select_for_update():
            success, _, message = OrderCompletionService.complete_order(order, save=True)
            
            if success:
                completed_count += 1
            else:
                failed_count += 1
                errors.append({'order_id': order.id, 'error': message})
        
        return {
            'completed_count': completed_count,
            'failed_count': failed_count,
            'total_processed': completed_count + failed_count,
            'errors': errors if errors else None,
        }


class RecommendationService:
    """
    Service class for generating personalized recommendations.
    Recommends best produce, farmers, and restaurants based on ratings, history, and compatibility.
    """
    
    @staticmethod
    def get_best_produce_for_restaurant(restaurant_user, limit=10):
        """
        Recommend the best produce items for a specific restaurant.
        Based on: freshness, farmer ratings, produce popularity, and restaurant type compatibility.
        
        Args:
            restaurant_user (User): Restaurant user instance
            limit (int): Number of recommendations to return
        
        Returns:
            list: List of dicts with produce info and recommendation score
        """
        if not restaurant_user or restaurant_user.role != 'restaurant':
            return []
        
        # Get all fresh, available produce from high-rated farmers
        produce_list = Produce.objects.filter(
            status='available',
            produce_state__in=['fresh', 'aging'],
            quantity__gt=0
        ).select_related('farmer').prefetch_related('orders')
        
        recommendations = []
        
        for produce in produce_list:
            # Farmer trust score
            farmer_trust = produce.farmer.trust_score if hasattr(produce.farmer, 'trust_score') else 5.0
            
            # Freshness score (0-10)
            freshness = produce.freshness_score
            
            # Demand forecast score (0-10)
            demand = produce.demand_forecast_score
            
            # Price reasonability (ratio to average similar items, lower is better)
            similar_produce = Produce.objects.filter(
                name__icontains=produce.name.split()[0],
                status='available'
            ).aggregate(Avg('price_per_kg'))
            avg_price = similar_produce['price_per_kg__avg'] or produce.price_per_kg
            price_factor = float(produce.price_per_kg) / float(avg_price)
            price_score = max(0, 10 - (price_factor * 5))  # Lower price = higher score
            
            # Availability (quantity available)
            availability = min(10.0, float(produce.quantity) / 50.0 * 10.0)
            
            # Composite recommendation score
            recommendation_score = (
                (farmer_trust / 10.0) * 0.25 +
                (freshness / 10.0) * 0.30 +
                (demand / 10.0) * 0.20 +
                (price_score / 10.0) * 0.15 +
                (availability / 10.0) * 0.10
            ) * 100
            
            recommendations.append({
                'produce_id': produce.id,
                'produce_name': produce.name,
                'farmer_id': produce.farmer.id,
                'farmer_name': produce.farmer.username,
                'price_per_kg': float(produce.price_per_kg),
                'freshness_score': round(freshness, 2),
                'freshness_grade': produce.freshness_grade,
                'farmer_trust_score': round(farmer_trust, 2),
                'quantity_available': float(produce.quantity),
                'demand_forecast': round(demand, 2),
                'recommendation_score': round(recommendation_score, 2),
                'reason': f"High quality from trusted farmer with good freshness",
            })
        
        # Sort by recommendation score
        recommendations.sort(key=lambda x: x['recommendation_score'], reverse=True)
        return recommendations[:limit]
    
    @staticmethod
    def get_best_farmers_for_restaurant(restaurant_user, limit=10):
        """
        Recommend the best farmers for a specific restaurant.
        Based on: farmer ratings, order history, delivery reliability, and product variety.
        
        Args:
            restaurant_user (User): Restaurant user instance
            limit (int): Number of recommendations to return
        
        Returns:
            list: List of dicts with farmer info and recommendation score
        """
        if not restaurant_user or restaurant_user.role != 'restaurant':
            return []
        
        # Get all farmers with available produce
        farmers = User.objects.filter(role='farmer').prefetch_related('produce_listings', 'received_orders')
        
        recommendations = []
        
        for farmer in farmers:
            # Farmer's trust score
            trust_score = farmer.trust_score if hasattr(farmer, 'trust_score') else 5.0
            
            # Count successful orders with restaurant
            past_orders = Order.objects.filter(
                farmer=farmer,
                restaurant=restaurant_user,
                status='completed'
            ).count()
            
            # Count total successful orders (reliability indicator)
            total_successful_orders = Order.objects.filter(
                farmer=farmer,
                status='completed'
            ).count()
            
            # Product variety (count unique produce items)
            product_variety = Produce.objects.filter(
                farmer=farmer,
                status='available'
            ).count()
            
            # Average freshness of available produce
            avg_freshness = Produce.objects.filter(
                farmer=farmer,
                status='available'
            ).aggregate(Avg('freshness_score'))['freshness_score__avg'] or 5.0
            
            # Get ratings for this farmer
            ratings = Rating.objects.filter(to_user=farmer)
            avg_rating = ratings.aggregate(Avg('score'))['score__avg'] or 3.0
            
            # Composite score
            recommendation_score = (
                (trust_score / 10.0) * 0.30 +
                (min(10, past_orders / 2.0 * 10.0) / 10.0) * 0.20 +
                (min(10, product_variety / 2.0) / 10.0) * 0.20 +
                (avg_freshness / 10.0) * 0.15 +
                (avg_rating / 5.0) * 0.15
            ) * 100
            
            # Only recommend farmers with some history or decent score
            if recommendation_score > 30 or past_orders > 0:
                recommendations.append({
                    'farmer_id': farmer.id,
                    'farmer_name': farmer.username,
                    'trust_score': round(trust_score, 2),
                    'average_rating': round(avg_rating, 2),
                    'past_orders_count': past_orders,
                    'total_successful_orders': total_successful_orders,
                    'product_variety': product_variety,
                    'average_freshness': round(avg_freshness, 2),
                    'recommendation_score': round(recommendation_score, 2),
                    'reason': f"Reliable farmer with {product_variety} products and {past_orders} past orders",
                })
        
        # Sort by recommendation score
        recommendations.sort(key=lambda x: x['recommendation_score'], reverse=True)
        return recommendations[:limit]
    
    @staticmethod
    def get_best_restaurants_for_farmer(farmer_user, limit=10):
        """
        Recommend the best restaurants for a farmer.
        Based on: restaurant ratings, order frequency, payment reliability, and order size.
        
        Args:
            farmer_user (User): Farmer user instance
            limit (int): Number of recommendations to return
        
        Returns:
            list: List of dicts with restaurant info and recommendation score
        """
        if not farmer_user or farmer_user.role != 'farmer':
            return []
        
        # Get all restaurants with which farmer has interacted or could interact
        all_restaurants = User.objects.filter(role='restaurant')
        
        recommendations = []
        
        for restaurant in all_restaurants:
            # Orders with this restaurant
            orders_with_restaurant = Order.objects.filter(
                farmer=farmer_user,
                restaurant=restaurant
            )
            
            completed_orders = orders_with_restaurant.filter(status='completed').count()
            total_orders = orders_with_restaurant.count()
            
            # Calculate completion rate
            completion_rate = (completed_orders / total_orders * 100) if total_orders > 0 else 0.0
            
            # Get restaurant's average rating (as buyer)
            restaurant_ratings = Rating.objects.filter(to_user=restaurant)
            avg_restaurant_rating = restaurant_ratings.aggregate(Avg('score'))['score__avg'] or 3.0
            
            # Average order value
            avg_order_value = orders_with_restaurant.filter(
                status='completed'
            ).aggregate(Avg('total_price'))['total_price__avg'] or 0.0
            
            # Order frequency (orders per month)
            if total_orders > 0:
                first_order = orders_with_restaurant.order_by('created_at').first()
                if first_order:
                    days_apart = (timezone.now() - first_order.created_at).days + 1
                    order_frequency = (total_orders / (days_apart / 30.0)) if days_apart > 0 else 0.0
                else:
                    order_frequency = 0.0
            else:
                order_frequency = 0.0
            
            # Recommendation score
            recommendation_score = (
                (completion_rate / 100.0) * 0.30 +
                (avg_restaurant_rating / 5.0) * 0.25 +
                (min(10, avg_order_value / 100.0) / 10.0) * 0.20 +
                (min(10, order_frequency / 2.0) / 10.0) * 0.25
            ) * 100
            
            # Recommend if there's history or decent score
            if recommendation_score > 30 or completed_orders > 0:
                recommendations.append({
                    'restaurant_id': restaurant.id,
                    'restaurant_name': restaurant.username,
                    'average_rating': round(avg_restaurant_rating, 2),
                    'completion_rate': round(completion_rate, 1),
                    'past_orders_count': completed_orders,
                    'total_orders': total_orders,
                    'average_order_value': round(float(avg_order_value), 2),
                    'order_frequency_per_month': round(order_frequency, 2),
                    'recommendation_score': round(recommendation_score, 2),
                    'reason': f"Reliable buyer with {completion_rate:.0f}% completion rate",
                })
        
        # Sort by recommendation score
        recommendations.sort(key=lambda x: x['recommendation_score'], reverse=True)
        return recommendations[:limit]


class DemandForecastService:
    """
    Service class for demand forecasting and trend analysis.
    Predicts demand based on historical orders, seasonality, and produce popularity.
    """
    
    DEMAND_FORECAST_DAYS = 30  # Look back 30 days for trends
    
    @staticmethod
    def calculate_demand_forecast(produce=None, period_days=30):
        """
        Calculate demand forecast for produce based on historical orders.
        
        Args:
            produce (Produce): Specific produce to forecast, or None for all produce
            period_days (int): Number of days to look back for trend analysis
        
        Returns:
            dict: Forecast metrics and prediction
        """
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=period_days)
        
        if produce:
            # Specific produce forecast
            orders = Order.objects.filter(
                produce=produce,
                status='completed',
                created_at__gte=cutoff_date
            )
        else:
            # All produce forecast
            orders = Order.objects.filter(
                status='completed',
                created_at__gte=cutoff_date
            )
        
        if not orders.exists():
            return {
                'total_orders': 0,
                'total_quantity': 0.0,
                'average_order_quantity': 0.0,
                'demand_score': 0.0,
                'forecast_trend': 'insufficient_data',
                'predicted_demand_next_week': 0.0,
            }
        
        # Calculate metrics
        total_orders = orders.count()
        total_quantity = orders.aggregate(Sum('quantity_requested'))['quantity_requested__sum'] or 0.0
        average_quantity = total_quantity / total_orders if total_orders > 0 else 0.0
        
        # Recent trend (last week vs previous weeks)
        recent_cutoff = timezone.now() - timedelta(days=7)
        recent_orders = orders.filter(created_at__gte=recent_cutoff).count()
        older_orders = orders.filter(created_at__lt=recent_cutoff).count()
        
        if older_orders > 0:
            trend_ratio = recent_orders / older_orders
        else:
            trend_ratio = 1.0 if recent_orders > 0 else 0.0
        
        # Determine trend
        if trend_ratio > 1.5:
            forecast_trend = 'increasing'
            trend_modifier = 1.3
        elif trend_ratio > 0.8:
            forecast_trend = 'stable'
            trend_modifier = 1.0
        else:
            forecast_trend = 'decreasing'
            trend_modifier = 0.7
        
        # Calculate demand score (0-10)
        # Based on order frequency
        demand_score = min(10.0, (total_orders / (period_days / 7.0)) / 2.0 * 10.0)
        
        # Predict next week demand
        average_weekly_orders = total_orders / (period_days / 7.0)
        predicted_demand_next_week = average_weekly_orders * trend_modifier
        
        return {
            'total_orders': total_orders,
            'total_quantity': round(float(total_quantity), 2),
            'average_order_quantity': round(average_quantity, 2),
            'demand_score': round(demand_score, 2),
            'forecast_trend': forecast_trend,
            'predicted_demand_next_week': round(predicted_demand_next_week, 2),
            'average_weekly_orders': round(average_weekly_orders, 2),
        }
    
    @staticmethod
    def get_produce_trend(limit=10):
        """
        Get trending produce items based on order volume and recency.
        
        Args:
            limit (int): Number of trending items to return
        
        Returns:
            list: List of trending produce with metrics
        """
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Count, Sum
        
        period_cutoff = timezone.now() - timedelta(days=30)
        
        # Get produce with completed orders in past 30 days
        trending = Produce.objects.filter(
            orders__status='completed',
            orders__created_at__gte=period_cutoff
        ).annotate(
            order_count=Count('orders'),
            total_quantity_sold=Sum('orders__quantity_requested')
        ).order_by('-order_count')[:limit]
        
        results = []
        for produce in trending:
            forecast = DemandForecastService.calculate_demand_forecast(produce)
            
            results.append({
                'produce_id': produce.id,
                'produce_name': produce.name,
                'farmer_id': produce.farmer.id,
                'farmer_name': produce.farmer.username,
                'order_count': produce.order_count or 0,
                'total_quantity_sold': round(float(produce.total_quantity_sold or 0), 2),
                'current_price': float(produce.price_per_kg),
                'freshness_grade': produce.freshness_grade,
                'demand_score': forecast['demand_score'],
                'forecast_trend': forecast['forecast_trend'],
                'predicted_demand_next_week': forecast['predicted_demand_next_week'],
                'popularity_rank': len(results) + 1,
            })
        
        return results
    
    @staticmethod
    def get_seasonal_demand_summary():
        """
        Get demand summary grouped by season.
        Helps identify seasonal trends and prepare for peak seasons.
        
        Returns:
            dict: Demand metrics grouped by season
        """
        from django.db.models import Count, Sum, Avg
        
        seasons = ['spring', 'summer', 'monsoon', 'autumn', 'winter', 'year_round']
        seasonal_summary = {}
        
        for season in seasons:
            # Get all produce for this season
            produce_in_season = Produce.objects.filter(season=season)
            
            if not produce_in_season.exists():
                continue
            
            # Get completed orders for this season's produce
            orders = Order.objects.filter(
                produce__in=produce_in_season,
                status='completed'
            )
            
            if not orders.exists():
                continue
            
            total_volume = orders.aggregate(Sum('quantity_requested'))['quantity_requested__sum'] or 0
            total_value = orders.aggregate(Sum('total_price'))['total_price__sum'] or 0
            avg_price = orders.aggregate(Avg('produce__price_per_kg'))['produce__price_per_kg__avg'] or 0
            
            seasonal_summary[season] = {
                'total_orders': orders.count(),
                'total_volume_kg': round(float(total_volume), 2),
                'total_value': round(float(total_value), 2),
                'average_price_per_kg': round(avg_price, 2),
                'unique_produce_types': produce_in_season.filter(orders__status='completed').distinct().count(),
                'farmer_count': produce_in_season.values('farmer').distinct().count(),
            }
        
        return seasonal_summary
    
    @staticmethod
    def get_restaurant_demand_profile(restaurant_user):
        """
        Get demand profile for a specific restaurant.
        Shows what produce they typically order and patterns.
        
        Args:
            restaurant_user (User): Restaurant user instance
        
        Returns:
            dict: Restaurant demand profile
        """
        from django.db.models import Count, Sum, Avg
        
        if not restaurant_user or restaurant_user.role != 'restaurant':
            return {}
        
        completed_orders = Order.objects.filter(
            restaurant=restaurant_user,
            status='completed'
        )
        
        if not completed_orders.exists():
            return {
                'restaurant_id': restaurant_user.id,
                'restaurant_name': restaurant_user.username,
                'order_history': 'No orders yet',
                'total_orders': 0,
                'total_volume_purchased': 0.0,
                'total_spending': 0.0,
                'favorite_produce': [],
                'preferred_farmers': [],
            }
        
        # Most ordered produce
        favorite_produce = completed_orders.values('produce__name', 'produce__id').annotate(
            count=Count('id'),
            total_qty=Sum('quantity_requested')
        ).order_by('-count')[:5]
        
        # Preferred farmers
        preferred_farmers = completed_orders.values('farmer__username', 'farmer__id').annotate(
            count=Count('id'),
            total_spending=Sum('total_price')
        ).order_by('-count')[:5]
        
        # Overall stats
        total_volume = completed_orders.aggregate(Sum('quantity_requested'))['quantity_requested__sum'] or 0
        total_spending = completed_orders.aggregate(Sum('total_price'))['total_price__sum'] or 0
        
        return {
            'restaurant_id': restaurant_user.id,
            'restaurant_name': restaurant_user.username,
            'total_orders': completed_orders.count(),
            'total_volume_purchased': round(float(total_volume), 2),
            'total_spending': round(float(total_spending), 2),
            'favorite_produce': [
                {
                    'produce_name': item['produce__name'],
                    'produce_id': item['produce__id'],
                    'order_count': item['count'],
                    'total_quantity': round(float(item['total_qty']), 2),
                }
                for item in favorite_produce
            ],
            'preferred_farmers': [
                {
                    'farmer_name': item['farmer__username'],
                    'farmer_id': item['farmer__id'],
                    'order_count': item['count'],
                    'total_spending': round(float(item['total_spending']), 2),
                }
                for item in preferred_farmers
            ],
        }

class NegotiationService:
    """
    Service class for managing order negotiations and counter-offers.
    Handles counter-offer creation, validation, acceptance, and expiry.
    """
    
    COUNTER_OFFER_EXPIRY_HOURS = 48  # Counter offers expire after 48 hours
    
    @staticmethod
    def create_counter_offer(order, proposed_quantity=None, proposed_unit_price=None,
                            proposed_delivery_date=None, reasoning="", created_by=None):
        """
        Create a counter-offer for an order.
        
        Args:
            order (Order): Order instance to counter-offer
            proposed_quantity (Decimal): Proposed quantity (optional, None keeps original)
            proposed_unit_price (Decimal): Proposed unit price (optional)
            proposed_delivery_date (Date): Proposed delivery date (optional)
            reasoning (str): Reason for the counter-offer
            created_by (User): User creating the counter-offer
        
        Returns:
            tuple: (success: bool, counter_offer: CounterOffer or None, message: str)
        """
        from .models import CounterOffer
        from datetime import timedelta
        
        if not order or not created_by:
            return False, None, "Order and creator required"
        
        # Check if counter-offer already exists and is pending
        existing_pending = CounterOffer.objects.filter(
            order=order,
            status='pending'
        ).first()
        
        if existing_pending and not existing_pending.is_expired():
            return False, existing_pending, "A pending counter-offer already exists"
        
        # Store original values if modifying
        if not order.original_unit_price and order.produce:
            order.original_unit_price = order.produce.price_per_kg
            order.original_total_price = order.total_price
            order.save()
        
        # Use proposed values or keep original
        quantity = proposed_quantity or order.quantity_requested
        unit_price = proposed_unit_price or (order.original_unit_price or order.produce.price_per_kg)
        total_price = quantity * unit_price
        
        # Create counter-offer
        counter_offer = CounterOffer.objects.create(
            order=order,
            created_by=created_by,
            proposed_quantity=quantity,
            proposed_unit_price=unit_price,
            proposed_total_price=total_price,
            proposed_delivery_date=proposed_delivery_date or order.preferred_delivery_date,
            reasoning=reasoning,
            status='pending',
            expires_at=timezone.now() + timedelta(hours=NegotiationService.COUNTER_OFFER_EXPIRY_HOURS)
        )
        
        # Update order negotiation status
        order.negotiation_status = 'counter_pending'
        order.negotiation_notes = reasoning
        order.save()
        
        return True, counter_offer, f"Counter-offer created and expires in {NegotiationService.COUNTER_OFFER_EXPIRY_HOURS} hours"
    
    @staticmethod
    def accept_counter_offer(counter_offer, accepted_by=None):
        """
        Accept a pending counter-offer.
        
        Args:
            counter_offer (CounterOffer): Counter-offer instance to accept
            accepted_by (User): User accepting the offer
        
        Returns:
            tuple: (success: bool, order: Order, message: str)
        """
        if not counter_offer:
            return False, None, "Counter-offer does not exist"
        
        # Check if valid for acceptance
        if counter_offer.is_expired():
            counter_offer.status = 'expired'
            counter_offer.save()
            return False, counter_offer.order, "Counter-offer has expired"
        
        if counter_offer.status != 'pending':
            return False, counter_offer.order, f"Counter-offer is already {counter_offer.status}"
        
        try:
            order = counter_offer.order
            
            # Update order with counter-offer details
            order.quantity_requested = counter_offer.proposed_quantity
            order.total_price = counter_offer.proposed_total_price
            order.preferred_delivery_date = counter_offer.proposed_delivery_date
            order.negotiation_status = 'counter_accepted'
            order.status = 'accepted'  # Move to accepted status
            
            # Update counter-offer
            counter_offer.status = 'accepted'
            counter_offer.responded_at = timezone.now()
            
            # Save all changes
            order.save()
            counter_offer.save()
            
            return True, order, "Counter-offer accepted and order updated"
        
        except Exception as e:
            return False, counter_offer.order, f"Error accepting counter-offer: {str(e)}"
    
    @staticmethod
    def reject_counter_offer(counter_offer, rejection_reason=""):
        """
        Reject a pending counter-offer.
        
        Args:
            counter_offer (CounterOffer): Counter-offer to reject
            rejection_reason (str): Reason for rejection
        
        Returns:
            tuple: (success: bool, message: str)
        """
        if not counter_offer:
            return False, "Counter-offer does not exist"
        
        if counter_offer.status != 'pending':
            return False, f"Cannot reject counter-offer with status '{counter_offer.status}'"
        
        try:
            order = counter_offer.order
            
            # Update counter-offer
            counter_offer.status = 'rejected'
            counter_offer.responded_at = timezone.now()
            counter_offer.reasoning = rejection_reason or counter_offer.reasoning
            
            # Update order back to pending/negotiation
            order.negotiation_status = 'counter_rejected'
            order.save()
            counter_offer.save()
            
            return True, "Counter-offer rejected"
        
        except Exception as e:
            return False, f"Error rejecting counter-offer: {str(e)}"
    
    @staticmethod
    def get_counter_offer_history(order):
        """
        Get all counter-offers for an order.
        
        Args:
            order (Order): Order instance
        
        Returns:
            list: List of counter-offers with details
        """
        from .models import CounterOffer
        
        counter_offers = CounterOffer.objects.filter(order=order).order_by('-created_at')
        
        results = []
        for co in counter_offers:
            results.append({
                'counter_offer_id': co.id,
                'created_by': co.created_by.username,
                'proposed_quantity': float(co.proposed_quantity or 0),
                'proposed_unit_price': float(co.proposed_unit_price or 0),
                'proposed_total_price': float(co.proposed_total_price or 0),
                'proposed_delivery_date': co.proposed_delivery_date,
                'status': co.status,
                'reasoning': co.reasoning,
                'is_expired': co.is_expired(),
                'created_at': co.created_at,
                'responded_at': co.responded_at,
            })
        
        return results
    
    @staticmethod
    def expire_old_counter_offers():
        """
        Mark old counter-offers as expired.
        Should be called periodically (e.g., hourly cron job).
        
        Returns:
            dict: Statistics of expiry operation
        """
        from .models import CounterOffer
        
        expired_count = 0
        
        pending_offers = CounterOffer.objects.filter(status='pending')
        for offer in pending_offers:
            if offer.is_expired():
                offer.status = 'expired'
                offer.save()
                expired_count += 1
        
        return {
            'expired_count': expired_count,
            'message': f"Marked {expired_count} counter-offers as expired"
        }


class DeliveryService:
    """
    Service class for managing delivery scheduling and windows.
    Handles preferred delivery slots, confirmations, and tracking.
    """
    
    @staticmethod
    def create_delivery_window(order, scheduled_date, time_slot_start, time_slot_end,
                              delivery_location="", special_instructions=""):
        """
        Create a delivery window for an order.
        
        Args:
            order (Order): Order instance
            scheduled_date (Date): Scheduled delivery date
            time_slot_start (Time): Delivery window start time
            time_slot_end (Time): Delivery window end time
            delivery_location (str): Delivery location address
            special_instructions (str): Special delivery instructions
        
        Returns:
            tuple: (success: bool, delivery_window: DeliveryWindow, message: str)
        """
        from .models import DeliveryWindow
        from datetime import datetime, timedelta
        
        if not order:
            return False, None, "Order does not exist"
        
        # Validate delivery date is in future
        if scheduled_date < timezone.now().date():
            return False, None, "Delivery date must be in the future"
        
        # Validate time range
        if time_slot_end <= time_slot_start:
            return False, None, "End time must be after start time"
        
        try:
            # Check if delivery window already exists
            existing = DeliveryWindow.objects.filter(order=order).first()
            if existing:
                existing.scheduled_date = scheduled_date
                existing.time_slot_start = time_slot_start
                existing.time_slot_end = time_slot_end
                existing.delivery_location = delivery_location
                existing.special_instructions = special_instructions
                existing.save()
                return True, existing, "Delivery window updated"
            
            # Create new delivery window
            delivery_window = DeliveryWindow.objects.create(
                order=order,
                scheduled_date=scheduled_date,
                time_slot_start=time_slot_start,
                time_slot_end=time_slot_end,
                delivery_location=delivery_location,
                special_instructions=special_instructions,
                estimated_arrival=timezone.make_aware(
                    datetime.combine(scheduled_date, time_slot_start)
                )
            )
            
            # Update order with delivery info
            order.preferred_delivery_date = scheduled_date
            order.preferred_delivery_time_start = time_slot_start
            order.preferred_delivery_time_end = time_slot_end
            order.delivery_address = delivery_location
            order.delivery_notes = special_instructions
            order.save()
            
            return True, delivery_window, "Delivery window created"
        
        except Exception as e:
            return False, None, f"Error creating delivery window: {str(e)}"
    
    @staticmethod
    def confirm_delivery(order, actual_delivery_datetime=None):
        """
        Confirm delivery of an order.
        
        Args:
            order (Order): Order instance
            actual_delivery_datetime (DateTime): Actual delivery time (defaults to now)
        
        Returns:
            tuple: (success: bool, message: str)
        """
        from .models import DeliveryWindow
        
        if not order:
            return False, "Order does not exist"
        
        try:
            # Update order
            order.actual_delivery_date = actual_delivery_datetime or timezone.now()
            order.status = 'completed'
            order.save()
            
            # Update delivery window if exists
            delivery_window = DeliveryWindow.objects.filter(order=order).first()
            if delivery_window:
                delivery_window.actual_arrival = order.actual_delivery_date
                delivery_window.delivery_confirmed = True
                delivery_window.save()
            
            return True, "Delivery confirmed"
        
        except Exception as e:
            return False, f"Error confirming delivery: {str(e)}"
    
    @staticmethod
    def get_delivery_schedule(farmer=None, restaurant=None, date_from=None, date_to=None):
        """
        Get delivery schedule for a farmer or restaurant.
        
        Args:
            farmer (User): Filter by farmer (optional)
            restaurant (User): Filter by restaurant (optional)
            date_from (Date): Start date filter (optional)
            date_to (Date): End date filter (optional)
        
        Returns:
            list: List of upcoming deliveries with details
        """
        from .models import DeliveryWindow
        
        # Build query
        query = DeliveryWindow.objects.filter(delivery_confirmed=False)
        
        if farmer:
            query = query.filter(order__farmer=farmer)
        
        if restaurant:
            query = query.filter(order__restaurant=restaurant)
        
        if date_from:
            query = query.filter(scheduled_date__gte=date_from)
        
        if date_to:
            query = query.filter(scheduled_date__lte=date_to)
        
        # Order by scheduled date
        query = query.order_by('scheduled_date', 'time_slot_start')
        
        results = []
        for delivery in query:
            results.append({
                'delivery_id': delivery.id,
                'order_id': delivery.order.id,
                'produce_name': delivery.order.produce.name,
                'farmer_name': delivery.order.farmer.username,
                'restaurant_name': delivery.order.restaurant.username,
                'quantity': float(delivery.order.quantity_requested),
                'scheduled_date': delivery.scheduled_date,
                'time_slot': f"{delivery.time_slot_start.strftime('%H:%M')} - {delivery.time_slot_end.strftime('%H:%M')}",
                'delivery_location': delivery.delivery_location,
                'special_instructions': delivery.special_instructions,
                'status': 'pending' if not delivery.delivery_confirmed else 'completed',
            })
        
        return results
    
    @staticmethod
    def get_delivery_time_slots(date, duration_minutes=30):
        """
        Generate available delivery time slots for a date.
        Simple approach: hourly slots from 6 AM to 8 PM.
        
        Args:
            date (Date): Date to generate slots for
            duration_minutes (int): Duration of each slot
        
        Returns:
            list: List of available time slots
        """
        from datetime import time, datetime, timedelta
        
        slots = []
        
        # Business hours: 6 AM to 8 PM
        start_hour = 6
        end_hour = 20
        
        current_time = time(start_hour, 0)
        slot_duration = timedelta(minutes=duration_minutes)
        
        while current_time.hour < end_hour:
            slot_end_hour = (current_time.hour + 1) % 24
            slot_end = time(slot_end_hour, 0)
            
            if slot_end_hour < current_time.hour:  # Wrapped to next day
                break
            
            slots.append({
                'start': current_time.strftime('%H:%M'),
                'end': slot_end.strftime('%H:%M'),
                'display': f"{current_time.strftime('%I:%M %p')} - {slot_end.strftime('%I:%M %p')}",
            })
            
            current_time = slot_end
        
        return slots
    
    @staticmethod
    def can_schedule_delivery(order, proposed_date):
        """
        Check if delivery can be scheduled for proposed date.
        
        Args:
            order (Order): Order instance
            proposed_date (Date): Proposed delivery date
        
        Returns:
            tuple: (can_schedule: bool, reason: str)
        """
        from datetime import timedelta
        
        if not order or not proposed_date:
            return False, "Order and date required"
        
        # Check if date is at least 1 day in future
        min_delivery_date = timezone.now().date() + timedelta(days=1)
        if proposed_date < min_delivery_date:
            return False, f"Delivery must be scheduled at least 1 day in advance"
        
        # Check if produce will still be fresh
        if order.produce and order.produce.expiry_date:
            days_until_expiry = (order.produce.expiry_date - proposed_date).days
            if days_until_expiry <= 0:
                return False, "Produce will be expired by delivery date"
        
        # Check produce state
        if order.produce and order.produce.produce_state in ['expired', 'unavailable']:
            return False, "Produce is not available for delivery"
        
        return True, "Delivery can be scheduled"


class AnalyticsService:
    """
    Service class for generating analytics and dashboard insights.
    Provides metrics, summaries, and recommended actions for farmers and restaurants.
    """
    
    @staticmethod
    def get_farmer_dashboard_analytics(farmer_user):
        """
        Get comprehensive analytics for farmer dashboard.
        
        Args:
            farmer_user (User): Farmer user instance
        
        Returns:
            dict: Complete analytics data
        """
        if not farmer_user or farmer_user.role != 'farmer':
            return {}
        
        # Order statistics
        all_orders = Order.objects.filter(farmer=farmer_user)
        completed_orders = all_orders.filter(status='completed').count()
        accepted_orders = all_orders.filter(status='accepted').count()
        pending_orders = all_orders.filter(status='pending').count()
        rejected_orders = all_orders.filter(status='rejected').count()
        total_orders = all_orders.count()
        
        # Calculate acceptance rate
        acceptance_rate = (accepted_orders / total_orders * 100) if total_orders > 0 else 0
        
        # Produce statistics
        produce_items = Produce.objects.filter(farmer=farmer_user)
        total_produce_count = produce_items.count()
        available_produce = produce_items.filter(status='available').count()
        sold_produce = produce_items.filter(status='sold').count()
        pending_produce = produce_items.filter(status='pending').count()
        
        # Freshness and spoilage metrics
        avg_freshness = produce_items.aggregate(Avg('freshness_score'))['freshness_score__avg'] or 0.0
        avg_spoilage = produce_items.aggregate(Avg('spoilage_risk_percentage'))['spoilage_risk_percentage__avg'] or 0.0
        
        # Calculate spoilage rate (produce in near_expiry or expired state)
        critical_produce = produce_items.filter(
            produce_state__in=['near_expiry', 'expired']
        ).count()
        spoilage_rate = (critical_produce / total_produce_count * 100) if total_produce_count > 0 else 0
        
        # Revenue metrics
        revenue = all_orders.filter(status='completed').aggregate(Sum('total_price'))['total_price__sum'] or 0
        avg_order_value = (revenue / completed_orders) if completed_orders > 0 else 0
        
        # Top produce
        top_produce = Produce.objects.filter(
            farmer=farmer_user,
            orders__status='completed'
        ).annotate(
            order_count=Count('orders')
        ).order_by('-order_count')[:5]
        
        top_produce_data = [
            {
                'name': p.name,
                'orders': p.order_count or 0,
                'price_per_kg': float(p.price_per_kg),
                'freshness_grade': p.freshness_grade,
            }
            for p in top_produce
        ]
        
        # Recommended top restaurants
        top_restaurants = Order.objects.filter(
            farmer=farmer_user,
            status='completed'
        ).values('restaurant__username', 'restaurant__id').annotate(
            count=Count('id'),
            total_value=Sum('total_price')
        ).order_by('-count')[:5]
        
        # Trust score
        trust_score = farmer_user.trust_score if hasattr(farmer_user, 'trust_score') else 5.0
        trust_level = TrustScoreService.get_user_trust_level(trust_score)
        
        # Recommended actions
        recommended_actions = []
        
        if spoilage_rate > 30:
            recommended_actions.append({
                'priority': 'high',
                'action': 'Review storage conditions',
                'reason': f"Spoilage rate at {spoilage_rate:.0f}% - Consider improving storage"
            })
        
        if acceptance_rate < 50 and total_orders > 5:
            recommended_actions.append({
                'priority': 'medium',
                'action': 'Review order terms',
                'reason': f"Low acceptance rate ({acceptance_rate:.0f}%) - Consider negotiating better terms"
            })
        
        if avg_freshness < 5:
            recommended_actions.append({
                'priority': 'high',
                'action': 'Improve harvest timing',
                'reason': f"Average freshness score low ({avg_freshness:.1f}/10)"
            })
        
        if pending_orders > 5:
            recommended_actions.append({
                'priority': 'medium',
                'action': 'Respond to pending orders',
                'reason': f"You have {pending_orders} pending orders waiting for response"
            })
        
        return {
            'summary': {
                'total_orders': total_orders,
                'completed_orders': completed_orders,
                'accepted_orders': accepted_orders,
                'pending_orders': pending_orders,
                'rejected_orders': rejected_orders,
                'acceptance_rate': round(acceptance_rate, 1),
            },
            'produce': {
                'total_count': total_produce_count,
                'available': available_produce,
                'sold': sold_produce,
                'pending': pending_produce,
                'avg_freshness': round(avg_freshness, 2),
                'avg_spoilage_risk': round(avg_spoilage, 1),
                'spoilage_rate': round(spoilage_rate, 1),
            },
            'revenue': {
                'total_revenue': round(float(revenue), 2),
                'avg_order_value': round(float(avg_order_value), 2),
                'total_completed_orders': completed_orders,
            },
            'top_produce': top_produce_data,
            'top_restaurants': [
                {
                    'name': r['restaurant__username'],
                    'orders': r['count'],
                    'total_value': round(float(r['total_value']), 2),
                }
                for r in top_restaurants
            ],
            'trust': {
                'score': round(trust_score, 2),
                'level': trust_level,
            },
            'recommended_actions': recommended_actions,
        }
    
    @staticmethod
    def get_restaurant_dashboard_analytics(restaurant_user):
        """
        Get comprehensive analytics for restaurant dashboard.
        
        Args:
            restaurant_user (User): Restaurant user instance
        
        Returns:
            dict: Complete analytics data
        """
        if not restaurant_user or restaurant_user.role != 'restaurant':
            return {}
        
        # Order statistics
        all_orders = Order.objects.filter(restaurant=restaurant_user)
        completed_orders = all_orders.filter(status='completed').count()
        accepted_orders = all_orders.filter(status='accepted').count()
        pending_orders = all_orders.filter(status='pending').count()
        rejected_orders = all_orders.filter(status='rejected').count()
        total_orders = all_orders.count()
        
        # Calculate fulfillment rate
        fulfillment_rate = (completed_orders / total_orders * 100) if total_orders > 0 else 0
        
        # Spending metrics
        total_spending = all_orders.filter(status='completed').aggregate(Sum('total_price'))['total_price__sum'] or 0
        avg_order_value = (total_spending / completed_orders) if completed_orders > 0 else 0
        
        # Available produce statistics
        available_produce = Produce.objects.filter(status='available', produce_state__in=['fresh', 'aging'])
        total_farmers = User.objects.filter(role='farmer').count()
        working_farmers = Order.objects.filter(restaurant=restaurant_user).values('farmer').distinct().count()
        
        # Top produce ordered
        top_produce = Order.objects.filter(
            restaurant=restaurant_user,
            status='completed'
        ).values('produce__name', 'produce__id').annotate(
            count=Count('id'),
            total_qty=Sum('quantity_requested'),
            avg_price=Avg('produce__price_per_kg'),
        ).order_by('-count')[:5]
        
        top_produce_data = [
            {
                'name': p['produce__name'],
                'orders': p['count'],
                'total_quantity': round(float(p['total_qty'] or 0), 2),
                'avg_price': round(float(p['avg_price'] or 0), 2),
            }
            for p in top_produce
        ]
        
        # Top farmers
        top_farmers = Order.objects.filter(
            restaurant=restaurant_user,
            status='completed'
        ).values('farmer__username', 'farmer__id').annotate(
            count=Count('id'),
            total_spent=Sum('total_price')
        ).order_by('-total_spent')[:5]
        
        top_farmers_data = [
            {
                'name': f['farmer__username'],
                'orders': f['count'],
                'total_spent': round(float(f['total_spent']), 2),
            }
            for f in top_farmers
        ]
        
        # Freshness preferences (quality of orders received)
        avg_freshness_received = Order.objects.filter(
            restaurant=restaurant_user,
            status='completed'
        ).aggregate(Avg('produce__freshness_score'))['produce__freshness_score__avg'] or 0.0
        
        # Trust score
        trust_score = restaurant_user.trust_score if hasattr(restaurant_user, 'trust_score') else 5.0
        trust_level = TrustScoreService.get_user_trust_level(trust_score)
        
        # Recommended actions
        recommended_actions = []
        
        if fulfillment_rate < 80 and total_orders > 5:
            recommended_actions.append({
                'priority': 'high',
                'action': 'Follow up on pending orders',
                'reason': f"Only {fulfillment_rate:.0f}% of orders fulfilled"
            })
        
        if working_farmers < 3:
            recommended_actions.append({
                'priority': 'medium',
                'action': 'Diversify farmer network',
                'reason': f"Working with only {working_farmers} farmer(s) - expand supplier relationships"
            })
        
        if available_produce.count() < 10:
            recommended_actions.append({
                'priority': 'low',
                'action': 'More produce available',
                'reason': f"Only {available_produce.count()} produce items available - explore more options"
            })
        
        if avg_freshness_received < 5:
            recommended_actions.append({
                'priority': 'medium',
                'action': 'Quality concerns',
                'reason': f"Average freshness score ({avg_freshness_received:.1f}/10) - discuss with farmers"
            })
        
        return {
            'summary': {
                'total_orders': total_orders,
                'completed_orders': completed_orders,
                'accepted_orders': accepted_orders,
                'pending_orders': pending_orders,
                'rejected_orders': rejected_orders,
                'fulfillment_rate': round(fulfillment_rate, 1),
            },
            'farmers': {
                'total_available': total_farmers,
                'working_with': working_farmers,
                'available_produce_count': available_produce.count(),
            },
            'spending': {
                'total_spending': round(float(total_spending), 2),
                'avg_order_value': round(float(avg_order_value), 2),
                'total_completed_orders': completed_orders,
            },
            'top_produce': top_produce_data,
            'top_farmers': top_farmers_data,
            'quality': {
                'avg_freshness_received': round(avg_freshness_received, 2),
            },
            'trust': {
                'score': round(trust_score, 2),
                'level': trust_level,
            },
            'recommended_actions': recommended_actions,
        }
    
    @staticmethod
    def get_forecast_highlights():
        """
        Get demand forecast highlights for the platform.
        Useful for both farmers and restaurants for planning.
        
        Returns:
            dict: Forecast data and insights
        """
        from datetime import timedelta
        
        # Trending produce
        trending = DemandForecastService.get_produce_trend(limit=5)
        
        # Seasonal summary
        seasonal = DemandForecastService.get_seasonal_demand_summary()
        
        # Recent orders trend
        recent_orders = Order.objects.filter(
            status='completed',
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        older_orders = Order.objects.filter(
            status='completed',
            created_at__gte=timezone.now() - timedelta(days=14),
            created_at__lt=timezone.now() - timedelta(days=7)
        ).count()
        
        if older_orders > 0:
            trend = 'increasing' if recent_orders > older_orders else ('stable' if recent_orders == older_orders else 'decreasing')
        else:
            trend = 'stable'
        
        highlights = []
        
        if trending:
            top_item = trending[0]
            highlights.append({
                'type': 'trending',
                'title': f"📈 {top_item['produce_name']} is trending",
                'description': f"{top_item['order_count']} orders in last 30 days",
                'recommendation': 'Focus on high-demand items for better sales'
            })
        
        if trend == 'increasing':
            highlights.append({
                'type': 'market_trend',
                'title': '📊 Market demand increasing',
                'description': f"Orders up {recent_orders - older_orders} week-over-week",
                'recommendation': 'Good time to increase production/orders'
            })
        
        return {
            'trending_produce': trending,
            'seasonal_demand': seasonal,
            'market_trend': trend,
            'highlights': highlights,
        }