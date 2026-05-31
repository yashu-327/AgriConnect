"""
Usage Examples for HackathonEnv

This file demonstrates how to use the AgriConnect Hackathon Environment
in different scenarios and with different agents.
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agriconnect.settings')
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))

import django
django.setup()

from hackathon.env import HackathonEnv
from hackathon.tasks import AgriConnectTasks


# ============================================================================
# Example 1: Basic Farmer Environment
# ============================================================================

def example_basic_farmer_env():
    """
    Example: Create a farmer environment, reset it, and take a few steps.
    """
    print("=" * 70)
    print("EXAMPLE 1: Basic Farmer Environment")
    print("=" * 70)
    
    # Create environment (will auto-create a test farmer user)
    env = HackathonEnv(agent_type='farmer')
    
    # Reset to start a new episode
    state = env.reset()
    print(f"\nInitial state:")
    print(f"  - Step: {state.step_count}")
    print(f"  - Farmers in platform: {len(state.farmers)}")
    print(f"  - Restaurants in platform: {len(state.restaurants)}")
    print(f"  - Active produce items: {len(state.produce_items)}")
    print(f"  - Active orders: {len(state.active_orders)}")
    
    # Take a few steps
    for step_num in range(3):
        print(f"\n--- Step {step_num + 1} ---")
        
        # Define an action (add produce)
        action = {
            'action_type': 'add_produce',
            'produce_name': f'Tomato Batch {step_num}',
            'quantity': 100 + (step_num * 10),
            'price': 50,
        }
        
        # Execute action
        output = env.step(action)
        
        print(f"  Action: {action['action_type']}")
        print(f"  Reward: {output.reward:.4f}")
        print(f"  Total Reward: {output.info['total_reward']:.4f}")
        print(f"  Done: {output.done}")


# ============================================================================
# Example 2: Restaurant Environment with Task
# ============================================================================

def example_restaurant_with_task():
    """
    Example: Create a restaurant environment with a specific task.
    """
    print("\n\n" + "=" * 70)
    print("EXAMPLE 2: Restaurant Environment with Task")
    print("=" * 70)
    
    # Create environment
    env = HackathonEnv(agent_type='restaurant')
    
    # Reset with specific task
    state = env.reset(task_id='restaurant_build_network')
    print(f"\nTask: {env.current_task['name']}")
    print(f"Objective: {env.current_task['description']}")
    print(f"Max steps: {env.max_steps}")
    
    # Simulate requesting produce from different farmers
    requests_made = 0
    for step_num in range(5):
        if state.produce_items and requests_made < 3:
            # Select a produce item to request
            produce = state.produce_items[step_num % len(state.produce_items)]
            
            action = {
                'action_type': 'request_produce',
                'produce_id': produce.id,
                'quantity': 15 + (step_num * 5),
            }
            
            print(f"\nStep {step_num + 1}:")
            print(f"  Requesting {action['quantity']} kg of {produce.name}")
            
            output = env.step(action)
            
            requests_made += 1
            print(f"  Reward: {output.reward:.4f}")
            
            # Update state if action was successful
            if output.info['action_result'].get('success'):
                state = output.state
    
    # Show task evaluation
    if output.task_progress:
        print(f"\nTask Evaluation:")
        print(f"  Success: {output.task_progress['success']}")
        print(f"  Score: {output.task_progress['score']:.2f}")
        print(f"  Reward: {output.task_progress['reward_earned']:.2f}")


# ============================================================================
# Example 3: Simple Agent Loop
# ============================================================================

def example_simple_agent_policy():
    """
    Example: Implement a simple agent policy and run an episode.
    """
    print("\n\n" + "=" * 70)
    print("EXAMPLE 3: Simple Agent Policy")
    print("=" * 70)
    
    class SimplePolicy:
        """Simple rule-based policy"""
        def __init__(self, agent_type):
            self.agent_type = agent_type
            self.step_count = 0
        
        def decide_action(self, state):
            """Decide action based on state"""
            self.step_count += 1
            
            if self.agent_type == 'farmer':
                # Farmer policy: add produce every other step
                if self.step_count % 2 == 0:
                    return {
                        'action_type': 'add_produce',
                        'produce_name': 'Lettuce',
                        'quantity': 50 + (self.step_count * 2),
                        'price': 40,
                    }
            else:
                # Restaurant policy: request from available produce
                if len(state.produce_items) > 0 and self.step_count % 2 == 0:
                    produce = state.produce_items[self.step_count % len(state.produce_items)]
                    return {
                        'action_type': 'request_produce',
                        'produce_id': produce.id,
                        'quantity': 10 + self.step_count,
                    }
            
            return {'action_type': 'noop'}
    
    # Create environment and policy
    env = HackathonEnv(agent_type='farmer')
    policy = SimplePolicy('farmer')
    
    # Run episode
    state = env.reset()
    episode_reward = 0
    
    print(f"\nRunning farmer episode with simple policy...")
    
    for episode_step in range(10):
        # Get action from policy
        action = policy.decide_action(state)
        
        # Execute action
        output = env.step(action)
        episode_reward += output.reward
        
        if (episode_step + 1) % 3 == 0:
            print(f"  Step {episode_step + 1}: Action={action['action_type']}, "
                  f"Reward={output.reward:.4f}, Total={episode_reward:.4f}")
        
        state = output.state
        
        if output.done:
            print(f"Episode done at step {episode_step + 1}")
            break
    
    print(f"\nFinal Episode Reward: {episode_reward:.4f}")


# ============================================================================
# Example 4: Multiple Simultaneous Environments
# ============================================================================

def example_multiple_environments():
    """
    Example: Run multiple environments in parallel (multi-agent simulation).
    """
    print("\n\n" + "=" * 70)
    print("EXAMPLE 4: Multiple Environments")
    print("=" * 70)
    
    # Create multiple environments
    num_farmers = 2
    num_restaurants = 2
    
    farmer_envs = [HackathonEnv(agent_type='farmer') for _ in range(num_farmers)]
    restaurant_envs = [HackathonEnv(agent_type='restaurant') for _ in range(num_restaurants)]
    
    # Reset all environments
    farmer_states = [env.reset() for env in farmer_envs]
    restaurant_states = [env.reset() for env in restaurant_envs]
    
    print(f"\nCreated {num_farmers} farmer and {num_restaurants} restaurant environments")
    
    # Run simulation for a few steps
    for step in range(5):
        print(f"\n--- Global Step {step + 1} ---")
        
        # Farmer actions
        for i, (env, state) in enumerate(zip(farmer_envs, farmer_states)):
            action = {
                'action_type': 'add_produce',
                'produce_name': f'Farmer{i}_Produce',
                'quantity': 50,
                'price': 45,
            }
            output = env.step(action)
            farmer_states[i] = output.state
            print(f"  Farmer {i}: Reward={output.reward:.4f}")
        
        # Restaurant actions
        for i, (env, state) in enumerate(zip(restaurant_envs, restaurant_states)):
            if state.produce_items:
                produce = state.produce_items[i % len(state.produce_items)]
                action = {
                    'action_type': 'request_produce',
                    'produce_id': produce.id,
                    'quantity': 20,
                }
                output = env.step(action)
                restaurant_states[i] = output.state
                print(f"  Restaurant {i}: Reward={output.reward:.4f}")


# ============================================================================
# Example 5: Accessing Detailed State Information
# ============================================================================

def example_state_inspection():
    """
    Example: Inspect detailed state information.
    """
    print("\n\n" + "=" * 70)
    print("EXAMPLE 5: State Inspection")
    print("=" * 70)
    
    env = HackathonEnv(agent_type='farmer')
    state = env.reset()
    
    print(f"\nEnvironment State Details:")
    print(f"\nFarmers ({len(state.farmers)}):")
    for farmer in state.farmers[:3]:
        print(f"  - {farmer.username}: {farmer.total_produce} produce items, "
              f"Trust={farmer.trust_score}, Orders={farmer.completed_orders}/{farmer.total_orders}")
    
    print(f"\nRestaurants ({len(state.restaurants)}):")
    for restaurant in state.restaurants[:3]:
        print(f"  - {restaurant.username}: {restaurant.completed_orders}/{restaurant.total_orders} orders, "
              f"Spending=${restaurant.total_spending:.2f}")
    
    print(f"\nProduce Items ({len(state.produce_items)}):")
    for produce in state.produce_items[:5]:
        print(f"  - {produce.name}: {produce.quantity} kg @ ${produce.price_per_kg}/kg, "
              f"Freshness={produce.freshness_score}, Spoilage Risk={produce.spoilage_risk:.1f}%")
    
    print(f"\nActive Orders ({len(state.active_orders)}):")
    for order in state.active_orders[:5]:
        print(f"  - {order.produce_name}: {order.quantity} kg, "
              f"Status={order.status}, Price=${order.total_price:.2f}")
    
    print(f"\nPlatform Metrics:")
    for key, value in state.platform_metrics.items():
        print(f"  - {key}: {value:.4f}")


# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    # Run examples
    example_basic_farmer_env()
    example_restaurant_with_task()
    example_simple_agent_policy()
    example_multiple_environments()
    example_state_inspection()
    
    print("\n\n" + "=" * 70)
    print("All examples completed!")
    print("=" * 70)
