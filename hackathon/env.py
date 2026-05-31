"""
AgriConnect Hackathon Environment
OpenEnv-compatible environment for hackathon challenges.
"""

import os
import sys
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agriconnect.settings')
django.setup()

from core.models import Order, Produce, User
from core.services import (
    AnalyticsService,
    OrderCompletionService,
    ProduceStateManager
)
from .schemas import (
    EnvironmentState,
    FarmerSnapshot,
    RestaurantSnapshot,
    ProduceSnapshot,
    OrderSnapshot,
    StepOutput,
    FarmerAction,
    RestaurantAction,
)
from .tasks import AgriConnectTasks, TaskGrader
from .rewards import RewardCalculator


class HackathonEnv:
    """
    AgriConnect OpenEnv-compatible environment.
    
    Usage:
        env = HackathonEnv(agent_type='farmer', agent_id=1)
        state = env.reset(task_id='farmer_maximize_revenue')
        
        for step in range(100):
            action = agent_policy(state)
            state, reward, done, info = env.step(action)
            if done:
                break
    """
    
    def __init__(
        self,
        agent_type: str = 'farmer',
        agent_id: Optional[int] = None,
        simulation_mode: bool = True
    ):
        """
        Initialize the environment.
        
        Args:
            agent_type: 'farmer' or 'restaurant'
            agent_id: User ID of agent (None = create test user)
            simulation_mode: Whether to use real DB or simulation
        """
        self.agent_type = agent_type
        self.agent_id = agent_id
        self.agent_user = None
        self.simulation_mode = simulation_mode
        
        self.current_task = None
        self.step_count = 0
        self.initial_state = None
        self.episode_rewards = []
        self.max_steps = 100
        
    def reset(self, task_id: Optional[str] = None) -> EnvironmentState:
        """
        Reset environment and start new episode.
        
        Args:
            task_id: Task to work on (optional)
        
        Returns:
            Initial EnvironmentState
        """
        # Get or create agent user
        if self.agent_id:
            self.agent_user = User.objects.get(id=self.agent_id)
        else:
            # Create test user
            test_username = f"test_{self.agent_type}_{datetime.now().timestamp()}"
            self.agent_user, _ = User.objects.get_or_create(
                username=test_username,
                defaults={
                    'email': f"{test_username}@test.local",
                    'role': self.agent_type,
                    'first_name': f"Test {self.agent_type.title()}",
                }
            )
        
        # Set task
        all_tasks = AgriConnectTasks.get_all_tasks()
        if task_id and task_id in all_tasks:
            self.current_task = all_tasks[task_id]
        elif self.agent_type == 'farmer':
            self.current_task = AgriConnectTasks.TASK_MAXIMIZE_REVENUE
        else:
            self.current_task = AgriConnectTasks.TASK_BUILD_NETWORK
        
        # Reset counters
        self.step_count = 0
        self.episode_rewards = []
        self.max_steps = self.current_task['max_steps']
        
        # Capture initial state
        state = self._get_state()
        self.initial_state = state
        
        return state
    
    def state(self) -> EnvironmentState:
        """
        Get current environment state.
        
        Returns:
            Current EnvironmentState
        """
        return self._get_state()
    
    def step(
        self,
        action: Dict[str, Any]
    ) -> StepOutput:
        """
        Take action in environment and return results.
        
        Args:
            action: Action dict with action_type and parameters
        
        Returns:
            StepOutput containing state, reward, done, info, task_progress
        """
        self.step_count += 1
        
        # Get pre-action state
        prev_state_dict = self._state_to_metrics()
        
        # Execute action
        action_result = self._execute_action(action)
        
        # Get post-action state  
        current_state = self._get_state()
        current_state_dict = self._state_to_metrics()
        
        # Calculate reward
        reward = RewardCalculator.calculate_step_reward(
            prev_state_dict,
            current_state_dict,
            {**action, 'agent_type': self.agent_type}
        )
        self.episode_rewards.append(reward)
        
        # Check if done
        done = self.step_count >= self.max_steps
        
        # Evaluate task progress
        task_eval = None
        if done and self.current_task:
            task_metrics = self._get_task_metrics()
            task_eval = TaskGrader.grade_task(
                self.current_task['id'],
                task_metrics,
                self.step_count
            )
            # Add task reward if successful
            if task_eval['success']:
                reward += task_eval['reward_earned'] / 30  # Distribute across steps
        
        return StepOutput(
            state=current_state,
            reward=reward,
            done=done,
            info={
                'step': self.step_count,
                'action_result': action_result,
                'total_reward': sum(self.episode_rewards),
                'avg_reward': sum(self.episode_rewards) / len(self.episode_rewards) if self.episode_rewards else 0,
            },
            task_progress=task_eval
        )
    
    # ===== Private Methods =====
    
    def _get_state(self) -> EnvironmentState:
        """Get complete environment state"""
        farmers = User.objects.filter(role='farmer')
        restaurants = User.objects.filter(role='restaurant')
        
        farmer_snapshots = [self._snapshot_farmer(f) for f in farmers[:5]]
        restaurant_snapshots = [self._snapshot_restaurant(r) for r in restaurants[:5]]
        
        produce_items = Produce.objects.filter(status='available')[:10]
        produce_snapshots = [self._snapshot_produce(p) for p in produce_items]
        
        orders = Order.objects.filter(status__in=['pending', 'accepted'])[:10]
        order_snapshots = [self._snapshot_order(o) for o in orders]
        
        metrics = self._calculate_platform_metrics()
        
        return EnvironmentState(
            step_count=self.step_count,
            timestamp=datetime.now().isoformat(),
            farmers=farmer_snapshots,
            restaurants=restaurant_snapshots,
            produce_items=produce_snapshots,
            active_orders=order_snapshots,
            platform_metrics=metrics,
        )
    
    def _snapshot_farmer(self, farmer: User) -> FarmerSnapshot:
        """Create snapshot of farmer"""
        produce = Produce.objects.filter(farmer=farmer)
        return FarmerSnapshot(
            user_id=farmer.id,
            username=farmer.username,
            total_produce=produce.count(),
            available_produce=produce.filter(status='available').count(),
            trust_score=farmer.trust_score,
            total_orders=Order.objects.filter(farmer=farmer).count(),
            completed_orders=Order.objects.filter(farmer=farmer, status='completed').count(),
        )
    
    def _snapshot_restaurant(self, restaurant: User) -> RestaurantSnapshot:
        """Create snapshot of restaurant"""
        orders = Order.objects.filter(restaurant=restaurant)
        return RestaurantSnapshot(
            user_id=restaurant.id,
            username=restaurant.username,
            total_orders=orders.count(),
            completed_orders=orders.filter(status='completed').count(),
            trust_score=restaurant.trust_score,
            total_spending=float(
                orders.filter(status='completed').aggregate(
                    models.Sum('total_price')
                )['total_price__sum'] or 0
            ),
            pending_orders=orders.filter(status='pending').count(),
        )
    
    def _snapshot_produce(self, produce: Produce) -> ProduceSnapshot:
        """Create snapshot of produce"""
        return ProduceSnapshot(
            id=produce.id,
            name=produce.name,
            quantity=float(produce.quantity),
            price_per_kg=float(produce.price_per_kg),
            freshness_score=produce.freshness_score,
            spoilage_risk=produce.spoilage_risk_percentage,
            produce_state=produce.produce_state,
            days_until_expiry=produce.days_until_expiry(),
        )
    
    def _snapshot_order(self, order: Order) -> OrderSnapshot:
        """Create snapshot of order"""
        days_pending = None
        if order.status == 'pending':
            days_pending = (datetime.now().replace(tzinfo=None) - order.created_at.replace(tzinfo=None)).days
        
        return OrderSnapshot(
            id=order.id,
            status=order.status,
            quantity=float(order.quantity_requested),
            total_price=float(order.total_price),
            produce_name=order.produce.name if order.produce else "Unknown",
            farmer_id=order.farmer.id,
            restaurant_id=order.restaurant.id,
            days_pending=days_pending,
        )
    
    def _execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute action and return result"""
        action_type = action.get('action_type', 'noop')
        result = {'success': False, 'action': action_type}
        
        try:
            if self.agent_type == 'farmer':
                result = self._execute_farmer_action(action)
            else:
                result = self._execute_restaurant_action(action)
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    def _execute_farmer_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute farmer action"""
        action_type = action.get('action_type', 'noop')
        
        if action_type == 'accept_order':
            order_id = action.get('target_order_id')
            if order_id:
                order = Order.objects.get(id=order_id)
                order.status = 'accepted'
                order.save()
                return {'success': True, 'message': f"Order {order_id} accepted"}
        
        elif action_type == 'add_produce':
            produce = Produce.objects.create(
                farmer=self.agent_user,
                name=action.get('produce_name', 'Unknown'),
                quantity=action.get('quantity', 0),
                price_per_kg=action.get('price', 0),
                availability_date=datetime.now().date(),
                status='available',
            )
            return {'success': True, 'produce_id': produce.id}
        
        return {'success': False, 'message': 'Unknown action'}
    
    def _execute_restaurant_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute restaurant action"""
        action_type = action.get('action_type', 'noop')
        
        if action_type == 'request_produce':
            produce_id = action.get('produce_id')
            quantity = action.get('quantity', 10)
            
            if produce_id:
                produce = Produce.objects.get(id=produce_id)
                order = Order.objects.create(
                    restaurant=self.agent_user,
                    farmer=produce.farmer,
                    produce=produce,
                    quantity_requested=quantity,
                    status='pending',
                )
                return {'success': True, 'order_id': order.id}
        
        return {'success': False, 'message': 'Unknown action'}
    
    def _state_to_metrics(self) -> Dict[str, Any]:
        """Convert state to simple metrics dict"""
        if self.agent_type == 'farmer':
            analytics = AnalyticsService.get_farmer_dashboard_analytics(self.agent_user)
            return {
                'completed_orders': analytics['summary']['completed_orders'],
                'total_revenue': analytics['revenue']['total_revenue'],
                'spoilage_rate': analytics['produce']['spoilage_rate'],
                'avg_freshness': analytics['produce']['avg_freshness'],
                'trust_score': analytics['trust']['score'],
                'acceptance_rate': analytics['summary']['acceptance_rate'] / 100,
            }
        else:
            analytics = AnalyticsService.get_restaurant_dashboard_analytics(self.agent_user)
            return {
                'completed_orders': analytics['summary']['completed_orders'],
                'unique_farmers': analytics['farmers']['working_with'],
                'trust_score': analytics['trust']['score'],
                'total_spending': analytics['spending']['total_spending'],
                'rejection_rate': 1 - (analytics['summary']['fulfillment_rate'] / 100),
                'avg_farmer_trust': 7.0,  # placeholder
            }
    
    def _get_task_metrics(self) -> Dict[str, Any]:
        """Get metrics for current task evaluation"""
        return self._state_to_metrics()
    
    def _calculate_platform_metrics(self) -> Dict[str, float]:
        """Calculate platform-wide metrics"""
        from django.db.models import Count, Sum, Avg, F
        
        total_orders = Order.objects.count()
        completed_orders = Order.objects.filter(status='completed').count()
        avg_freshness = Produce.objects.aggregate(Avg('freshness_score'))['freshness_score__avg'] or 0
        
        return {
            'total_orders': float(total_orders),
            'completion_rate': float(completed_orders / total_orders) if total_orders > 0 else 0,
            'avg_freshness': float(avg_freshness),
            'platform_revenue': float(
                Order.objects.filter(status='completed').aggregate(
                    Sum('total_price')
                )['total_price__sum'] or 0
            ),
        }


# Compatibility import for Django
from django.db import models
