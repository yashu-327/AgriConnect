"""
AgriConnect Hackathon Environment - Type Schemas
Defines typed data structures for environment state, actions, and observations.
"""

from typing import TypedDict, Optional, List, Dict, Any
from decimal import Decimal


class ProduceSnapshot(TypedDict):
    """Snapshot of a produce item"""
    id: int
    name: str
    quantity: float
    price_per_kg: float
    freshness_score: float
    spoilage_risk: float
    produce_state: str
    days_until_expiry: Optional[int]


class FarmerSnapshot(TypedDict):
    """Snapshot of a farmer's account"""
    user_id: int
    username: str
    total_produce: int
    available_produce: int
    trust_score: float
    total_orders: int
    completed_orders: int


class RestaurantSnapshot(TypedDict):
    """Snapshot of a restaurant account"""
    user_id: int
    username: str
    total_orders: int
    completed_orders: int
    trust_score: float
    total_spending: float
    pending_orders: int


class OrderSnapshot(TypedDict):
    """Snapshot of an order"""
    id: int
    status: str
    quantity: float
    total_price: float
    produce_name: str
    farmer_id: int
    restaurant_id: int
    days_pending: Optional[int]


class EnvironmentState(TypedDict):
    """Complete environment state at a point in time"""
    step_count: int
    timestamp: str
    farmers: List[FarmerSnapshot]
    restaurants: List[RestaurantSnapshot]
    produce_items: List[ProduceSnapshot]
    active_orders: List[OrderSnapshot]
    platform_metrics: Dict[str, float]


class FarmerAction(TypedDict):
    """Action taken by a farmer agent"""
    action_type: str  # 'accept_order', 'reject_order', 'add_produce', 'negotiate'
    target_order_id: Optional[int]
    produce_name: Optional[str]
    quantity: Optional[float]
    price: Optional[float]
    counter_offer_terms: Optional[Dict[str, Any]]


class RestaurantAction(TypedDict):
    """Action taken by a restaurant agent"""
    action_type: str  # 'request_produce', 'accept_offer', 'reject_offer', 'negotiate'
    produce_id: Optional[int]
    quantity: Optional[float]
    preferred_delivery_date: Optional[str]
    counter_terms: Optional[Dict[str, Any]]


class TaskObjective(TypedDict):
    """Task objective definition"""
    id: str
    name: str
    description: str
    agent_type: str  # 'farmer' or 'restaurant'
    success_criteria: Dict[str, Any]
    max_steps: int
    reward_on_success: float


class TaskEvaluation(TypedDict):
    """Evaluation result for a task"""
    task_id: str
    completed: bool
    success: bool
    steps_taken: int
    reward_earned: float
    metrics: Dict[str, float]
    feedback: str


class StepOutput(TypedDict):
    """Output from environment.step()"""
    state: EnvironmentState
    reward: float
    done: bool
    info: Dict[str, Any]
    task_progress: Optional[TaskEvaluation]
