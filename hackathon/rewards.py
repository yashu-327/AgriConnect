"""
AgriConnect Hackathon Reward Function
Calculates rewards based on environment transitions and actions.
"""

from typing import Dict, Any
from .schemas import EnvironmentState


class RewardCalculator:
    """Calculates rewards for agent actions in AgriConnect"""
    
    # Reward constants
    ORDER_COMPLETED_REWARD = 50.0
    ORDER_ACCEPTED_REWARD = 10.0
    ORDER_REJECTED_PENALTY = -5.0
    
    SPOILAGE_PENALTY_PER_PERCENT = -2.0  # Penalty for each % of spoilage
    FRESHNESS_BONUS_PER_POINT = 5.0  # Bonus for freshness >= 8.0
    
    TRUST_INCREASE_REWARD = 15.0
    NEGOTIATION_SUCCESS_REWARD = 20.0
    
    DELIVERY_ON_TIME_REWARD = 25.0
    DELIVERY_LATE_PENALTY = -15.0
    
    NETWORK_FARMER_BONUS = 30.0  # For each new farmer connection
    REVENUE_PER_1000_BONUS = 2.0  # ₹1000 revenue = 2 points
    
    @staticmethod
    def calculate_order_reward(
        order_status: str,
        freshness_score: float,
        spoilage_risk: float,
        days_delayed: int = 0
    ) -> float:
        """
        Calculate reward for order completion.
        
        Args:
            order_status: 'completed', 'accepted', 'rejected'
            freshness_score: 0-10 freshness score
            spoilage_risk: 0-100 spoilage risk percentage
            days_delayed: days late for delivery
        
        Returns:
            Reward value
        """
        reward = 0.0
        
        if order_status == 'completed':
            reward += RewardCalculator.ORDER_COMPLETED_REWARD
            
            # Freshness bonus
            if freshness_score >= 8.0:
                reward += (freshness_score - 7.0) * RewardCalculator.FRESHNESS_BONUS_PER_POINT
            
            # Spoilage penalty
            reward += spoilage_risk * RewardCalculator.SPOILAGE_PENALTY_PER_PERCENT
            
            # Delivery timing
            if days_delayed <= 0:
                reward += RewardCalculator.DELIVERY_ON_TIME_REWARD
            else:
                reward -= days_delayed * RewardCalculator.DELIVERY_LATE_PENALTY
        
        elif order_status == 'accepted':
            reward += RewardCalculator.ORDER_ACCEPTED_REWARD
        
        elif order_status == 'rejected':
            reward += RewardCalculator.ORDER_REJECTED_PENALTY
        
        return max(-100, reward)  # Clip to reasonable bounds
    
    @staticmethod
    def calculate_revenue_reward(
        new_revenue: float,
        old_revenue: float = 0.0
    ) -> float:
        """
        Calculate reward for revenue generation.
        
        Args:
            new_revenue: Current total revenue
            old_revenue: Previous total revenue
        
        Returns:
            Reward value
        """
        revenue_delta = new_revenue - old_revenue
        reward = (revenue_delta / 1000.0) * RewardCalculator.REVENUE_PER_1000_BONUS
        return reward
    
    @staticmethod
    def calculate_network_reward(
        new_farmer_count: int,
        old_farmer_count: int
    ) -> float:
        """
        Calculate reward for building restaurant network.
        
        Args:
            new_farmer_count: Current number of farmer connections
            old_farmer_count: Previous farmer count
        
        Returns:
            Reward value
        """
        new_connections = max(0, new_farmer_count - old_farmer_count)
        reward = new_connections * RewardCalculator.NETWORK_FARMER_BONUS
        return reward
    
    @staticmethod
    def calculate_trust_reward(
        new_trust_score: float,
        old_trust_score: float
    ) -> float:
        """
        Calculate reward for trust score increase.
        
        Args:
            new_trust_score: Current trust score
            old_trust_score: Previous trust score
        
        Returns:
            Reward value
        """
        if new_trust_score > old_trust_score:
            trust_delta = new_trust_score - old_trust_score
            reward = trust_delta * RewardCalculator.TRUST_INCREASE_REWARD
            return reward
        return 0.0
    
    @staticmethod
    def calculate_spoilage_reward(spoilage_rate: float) -> float:
        """
        Calculate penalty for high spoilage.
        
        Args:
            spoilage_rate: Percentage of produce spoiled (0-100)
        
        Returns:
            Reward value (negative)
        """
        if spoilage_rate > 30:
            # Heavy penalty for excessive spoilage
            return -(spoilage_rate - 30) * 2.0
        elif spoilage_rate > 10:
            return -(spoilage_rate - 10) * 1.0
        return 0.0
    
    @staticmethod
    def calculate_step_reward(
        prev_state: Dict[str, Any],
        current_state: Dict[str, Any],
        action: Dict[str, Any]
    ) -> float:
        """
        Calculate total reward for a single environment step.
        
        Args:
            prev_state: State before action
            current_state: State after action
            action: Action taken
        
        Returns:
            Total reward for step
        """
        reward = 0.0
        
        # Get agent type from action (if available)
        agent_type = action.get('agent_type', 'unknown')
        
        # Order completion rewards
        if agent_type == 'farmer':
            # Check for newly completed orders
            prev_completed = prev_state.get('completed_orders', 0)
            curr_completed = current_state.get('completed_orders', 0)
            
            if curr_completed > prev_completed:
                orders_completed = curr_completed - prev_completed
                avg_freshness = current_state.get('avg_freshness', 5.0)
                spoilage = current_state.get('spoilage_rate', 50.0)
                reward += orders_completed * RewardCalculator.calculate_order_reward(
                    'completed', avg_freshness, spoilage
                )
            
            # Revenue reward
            prev_revenue = prev_state.get('total_revenue', 0.0)
            curr_revenue = current_state.get('total_revenue', 0.0)
            reward += RewardCalculator.calculate_revenue_reward(curr_revenue, prev_revenue)
            
            # Spoilage penalty
            reward += RewardCalculator.calculate_spoilage_reward(
                current_state.get('spoilage_rate', 0.0)
            )
            
            # Trust increase
            prev_trust = prev_state.get('trust_score', 5.0)
            curr_trust = current_state.get('trust_score', 5.0)
            reward += RewardCalculator.calculate_trust_reward(curr_trust, prev_trust)
        
        elif agent_type == 'restaurant':
            # Network building reward
            prev_farmers = prev_state.get('unique_farmers', 0)
            curr_farmers = current_state.get('unique_farmers', 0)
            reward += RewardCalculator.calculate_network_reward(curr_farmers, prev_farmers)
            
            # Completed orders reward
            prev_completed = prev_state.get('completed_orders', 0)
            curr_completed = current_state.get('completed_orders', 0)
            
            if curr_completed > prev_completed:
                orders_completed = curr_completed - prev_completed
                reward += orders_completed * RewardCalculator.ORDER_COMPLETED_REWARD
            
            # Trust increase
            prev_trust = prev_state.get('trust_score', 5.0)
            curr_trust = current_state.get('trust_score', 5.0)
            reward += RewardCalculator.calculate_trust_reward(curr_trust, prev_trust)
        
        # Small step penalty to encourage efficient solutions
        reward -= 0.1
        
        return reward
    
    @staticmethod
    def get_reward_summary(step_rewards: list) -> Dict[str, float]:
        """
        Summarize accumulated rewards.
        
        Args:
            step_rewards: List of rewards per step
        
        Returns:
            Summary statistics
        """
        if not step_rewards:
            return {
                'total': 0.0,
                'average': 0.0,
                'max': 0.0,
                'min': 0.0,
                'steps': 0
            }
        
        return {
            'total': sum(step_rewards),
            'average': sum(step_rewards) / len(step_rewards),
            'max': max(step_rewards),
            'min': min(step_rewards),
            'steps': len(step_rewards)
        }
