"""
Test suite for HackathonEnv
"""

import os
import sys
import django
import unittest
import uuid
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agriconnect.settings')
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))
django.setup()

from datetime import datetime

from django.test import TestCase
from core.models import User, Produce, Order
from .env import HackathonEnv
from .tasks import AgriConnectTasks


class TestHackathonEnv(TestCase):
    """Test HackathonEnv functionality"""
    
    def setUp(self):
        """Set up test environment"""
        unique_suffix = uuid.uuid4().hex[:8]
        # Create test users
        self.farmer = User.objects.create_user(
            username=f'test_farmer_{unique_suffix}',
            email='farmer@test.local',
            password='testpass123',
            role='farmer',
            first_name='Test',
            last_name='Farmer'
        )
        
        self.restaurant = User.objects.create_user(
            username=f'test_restaurant_{unique_suffix}',
            email='restaurant@test.local',
            password='testpass123',
            role='restaurant',
            first_name='Test',
            last_name='Restaurant'
        )
        
        # Create test produce
        self.produce = Produce.objects.create(
            farmer=self.farmer,
            name='Tomato',
            quantity=100,
            price_per_kg=50,
            freshness_score=9.0,
            availability_date=datetime.now().date(),
            status='available'
        )
    
    def test_env_initialization(self):
        """Test environment initialization"""
        env = HackathonEnv(agent_type='farmer', agent_id=self.farmer.id)
        self.assertEqual(env.agent_type, 'farmer')
        self.assertEqual(env.agent_id, self.farmer.id)
    
    def test_reset_returns_state(self):
        """Test reset returns valid state"""
        env = HackathonEnv(agent_type='farmer', agent_id=self.farmer.id)
        state = env.reset(task_id='farmer_maximize_revenue')
        
        self.assertIsNotNone(state)
        self.assertEqual(state['step_count'], 0)
        self.assertIsNotNone(state['timestamp'])
        self.assertIsNotNone(state['farmers'])
        self.assertIsNotNone(state['restaurants'])
    
    def test_step_returns_step_output(self):
        """Test step returns valid StepOutput"""
        env = HackathonEnv(agent_type='farmer', agent_id=self.farmer.id)
        env.reset()
        
        action = {
            'action_type': 'add_produce',
            'produce_name': 'Potato',
            'quantity': 50,
            'price': 30,
        }
        
        output = env.step(action)
        
        self.assertIsNotNone(output['state'])
        self.assertEqual(output['state']['step_count'], 1)
        self.assertIsNotNone(output['reward'])
        self.assertIsNotNone(output['info'])
    
    def test_farmer_accept_order_action(self):
        """Test farmer accepting order"""
        # Create an order
        order = Order.objects.create(
            farmer=self.farmer,
            restaurant=self.restaurant,
            produce=self.produce,
            quantity_requested=10,
            status='pending'
        )
        
        env = HackathonEnv(agent_type='farmer', agent_id=self.farmer.id)
        env.reset()
        
        action = {
            'action_type': 'accept_order',
            'target_order_id': order.id,
        }
        
        output = env.step(action)
        
        # Verify order was accepted
        order.refresh_from_db()
        self.assertEqual(order.status, 'accepted')
    
    def test_restaurant_request_produce_action(self):
        """Test restaurant requesting produce"""
        env = HackathonEnv(agent_type='restaurant', agent_id=self.restaurant.id)
        env.reset()
        
        action = {
            'action_type': 'request_produce',
            'produce_id': self.produce.id,
            'quantity': 25,
        }
        
        output = env.step(action)
        
        # Verify order was created
        order = Order.objects.filter(restaurant=self.restaurant).first()
        self.assertIsNotNone(order)
        self.assertEqual(order.quantity_requested, 25)
        self.assertEqual(order.status, 'pending')
    
    def test_done_flag_after_max_steps(self):
        """Test done flag is set after max steps"""
        env = HackathonEnv(agent_type='farmer', agent_id=self.farmer.id)
        env.reset()
        
        # Run steps until done
        action = {'action_type': 'noop'}
        for i in range(env.max_steps):
            output = env.step(action)
            if output['done']:
                self.assertEqual(env.step_count, env.max_steps)
                break
    
    def test_state_method(self):
        """Test state() method returns current state"""
        env = HackathonEnv(agent_type='farmer', agent_id=self.farmer.id)
        env.reset()
        
        state = env.state()
        
        self.assertIsNotNone(state)
        self.assertEqual(state['step_count'], 0)
    
    def test_episode_rewards_accumulation(self):
        """Test episode rewards accumulate"""
        env = HackathonEnv(agent_type='farmer', agent_id=self.farmer.id)
        env.reset()
        
        action = {'action_type': 'noop'}
        previous_total = 0.0
        
        for _ in range(5):
            output = env.step(action)
            self.assertIsInstance(output['info']['total_reward'], float)
            self.assertEqual(output['info']['total_reward'], previous_total + output['reward'])
            previous_total = output['info']['total_reward']


class TestHackathonEnvWithoutAgent(TestCase):
    """Test environment creation without specifying agent"""
    
    def test_auto_create_farmer_agent(self):
        """Test auto-creation of farmer agent"""
        env = HackathonEnv(agent_type='farmer')
        state = env.reset()
        
        self.assertIsNotNone(env.agent_user)
        self.assertEqual(env.agent_user.role, 'farmer')
        self.assertIsNotNone(state)
    
    def test_auto_create_restaurant_agent(self):
        """Test auto-creation of restaurant agent"""
        env = HackathonEnv(agent_type='restaurant')
        state = env.reset()
        
        self.assertIsNotNone(env.agent_user)
        self.assertEqual(env.agent_user.role, 'restaurant')
        self.assertIsNotNone(state)


class TestIntegration(TestCase):
    """Integration tests"""
    
    def setUp(self):
        """Set up test environment"""
        unique_suffix = uuid.uuid4().hex[:8]
        # Create multiple users and produce
        self.farmers = []
        for i in range(3):
            farmer = User.objects.create_user(
                username=f'farmer_{unique_suffix}_{i}',
                email=f'farmer{i}@test.local',
                password='testpass123',
                role='farmer'
            )
            self.farmers.append(farmer)
        
        self.restaurants = []
        for i in range(2):
            restaurant = User.objects.create_user(
                username=f'restaurant_{unique_suffix}_{i}',
                email=f'restaurant{i}@test.local',
                password='testpass123',
                role='restaurant'
            )
            self.restaurants.append(restaurant)
        
        # Create produce
        self.produce_items = []
        for farmer in self.farmers:
            for i in range(2):
                p = Produce.objects.create(
                    farmer=farmer,
                    name=f'Produce_{i}',
                    quantity=100,
                    price_per_kg=50,
                    freshness_score=8.0,
                    availability_date=datetime.now().date(),
                    status='available'
                )
                self.produce_items.append(p)
    
    def test_full_farmer_episode(self):
        """Test full farmer episode"""
        env = HackathonEnv(agent_type='farmer', agent_id=self.farmers[0].id)
        state = env.reset(task_id='farmer_maximize_revenue')
        
        total_reward = 0
        for step in range(10):
            action = {
                'action_type': 'add_produce' if step % 3 == 0 else 'noop',
                'produce_name': 'Potato',
                'quantity': 100,
                'price': 30,
            }
            
            output = env.step(action)
            total_reward += output['reward']
            
            if output['done']:
                break
        
        self.assertIsInstance(total_reward, float)
        self.assertGreater(len(env.episode_rewards), 0)
    
    def test_full_restaurant_episode(self):
        """Test full restaurant episode"""
        env = HackathonEnv(agent_type='restaurant', agent_id=self.restaurants[0].id)
        state = env.reset(task_id='restaurant_build_network')
        
        for step in range(10):
            if self.produce_items:
                action = {
                    'action_type': 'request_produce',
                    'produce_id': self.produce_items[step % len(self.produce_items)].id,
                    'quantity': 20,
                }
            else:
                action = {'action_type': 'noop'}
            
            output = env.step(action)
            
            if output['done']:
                break


if __name__ == '__main__':
    unittest.main()
