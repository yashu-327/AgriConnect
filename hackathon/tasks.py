"""
AgriConnect Hackathon Tasks
Defines graded tasks for farmers and restaurants to complete.
"""

from typing import Dict, Any, Tuple
from enum import Enum
from .schemas import TaskObjective, TaskEvaluation


class TaskDifficulty(Enum):
    """Task difficulty levels"""
    EASY = 1
    MEDIUM = 2
    HARD = 3


class AgriConnectTasks:
    """Collection of graded tasks for the hackathon"""
    
    # Task 1: Farmer - Maximize Revenue
    TASK_MAXIMIZE_REVENUE = TaskObjective(
        id="farmer_maximize_revenue",
        name="🌾 Maximize Farm Revenue",
        description="Increase total revenue from completed orders to at least ₹10,000 within 30 days",
        agent_type="farmer",
        success_criteria={
            "min_revenue": 10000,
            "min_orders": 5,
            "min_completion_rate": 0.8,
            "max_spoilage_rate": 20.0,
        },
        max_steps=30,
        reward_on_success=1000.0,
    )
    
    # Task 2: Restaurant - Build Trusted Farmer Network
    TASK_BUILD_NETWORK = TaskObjective(
        id="restaurant_build_network",
        name="🤝 Build Trusted Farmer Network",
        description="Establish relationships with at least 5 farmers with avg trust score > 7.0",
        agent_type="restaurant",
        success_criteria={
            "min_farmers": 5,
            "min_avg_trust": 7.0,
            "min_completed_orders": 10,
            "max_rejection_rate": 0.2,
        },
        max_steps=30,
        reward_on_success=800.0,
    )
    
    # Task 3: Farmer - Reduce Spoilage Rate
    TASK_REDUCE_SPOILAGE = TaskObjective(
        id="farmer_reduce_spoilage",
        name="🏆 Master Fresh Produce Management",
        description="Maintain a spoilage rate below 10% while fulfilling at least 8 orders",
        agent_type="farmer",
        success_criteria={
            "max_spoilage_rate": 10.0,
            "min_orders": 8,
            "min_freshness_avg": 7.0,
            "min_order_acceptance": 0.75,
        },
        max_steps=30,
        reward_on_success=900.0,
    )
    
    @staticmethod
    def get_all_tasks() -> Dict[str, TaskObjective]:
        """Get all available tasks"""
        return {
            AgriConnectTasks.TASK_MAXIMIZE_REVENUE['id']: AgriConnectTasks.TASK_MAXIMIZE_REVENUE,
            AgriConnectTasks.TASK_BUILD_NETWORK['id']: AgriConnectTasks.TASK_BUILD_NETWORK,
            AgriConnectTasks.TASK_REDUCE_SPOILAGE['id']: AgriConnectTasks.TASK_REDUCE_SPOILAGE,
        }
    
    @staticmethod
    def get_farmer_tasks() -> Dict[str, TaskObjective]:
        """Get all farmer tasks"""
        all_tasks = AgriConnectTasks.get_all_tasks()
        return {k: v for k, v in all_tasks.items() if v['agent_type'] == 'farmer'}
    
    @staticmethod
    def get_restaurant_tasks() -> Dict[str, TaskObjective]:
        """Get all restaurant tasks"""
        all_tasks = AgriConnectTasks.get_all_tasks()
        return {k: v for k, v in all_tasks.items() if v['agent_type'] == 'restaurant'}


class TaskGrader:
    """Grades task completion and provides feedback"""
    
    @staticmethod
    def grade_maximize_revenue(metrics: Dict[str, Any]) -> Tuple[bool, float, str]:
        """
        Grade: Maximize Farm Revenue task
        
        Returns: (success, score_multiplier, feedback)
        """
        revenue = metrics.get('total_revenue', 0)
        orders = metrics.get('completed_orders', 0)
        completion_rate = metrics.get('completion_rate', 0)
        spoilage_rate = metrics.get('spoilage_rate', 100)
        
        criteria = AgriConnectTasks.TASK_MAXIMIZE_REVENUE['success_criteria']
        
        feedbacks = []
        score = 0
        
        # Revenue check
        if revenue >= criteria['min_revenue']:
            score += 0.4
            feedbacks.append(f"✅ Revenue target met: ₹{revenue}")
        else:
            score += (revenue / criteria['min_revenue']) * 0.4
            feedbacks.append(f"📊 Revenue: ₹{revenue}/{criteria['min_revenue']}")
        
        # Orders check
        if orders >= criteria['min_orders']:
            score += 0.2
            feedbacks.append(f"✅ Order target met: {orders} orders")
        else:
            score += (orders / criteria['min_orders']) * 0.2
            feedbacks.append(f"📦 Orders: {orders}/{criteria['min_orders']}")
        
        # Completion rate
        if completion_rate >= criteria['min_completion_rate']:
            score += 0.2
            feedbacks.append(f"✅ High completion rate: {completion_rate*100:.0f}%")
        else:
            score += completion_rate * 0.2
            feedbacks.append(f"⏱️ Completion rate: {completion_rate*100:.0f}%")
        
        # Spoilage rate
        if spoilage_rate <= criteria['max_spoilage_rate']:
            score += 0.2
            feedbacks.append(f"✅ Low spoilage: {spoilage_rate:.1f}%")
        else:
            score = max(0, score - 0.1)
            feedbacks.append(f"⚠️ High spoilage: {spoilage_rate:.1f}%")
        
        success = score >= 0.85
        feedback = "\n".join(feedbacks)
        
        return success, score, feedback
    
    @staticmethod
    def grade_build_network(metrics: Dict[str, Any]) -> Tuple[bool, float, str]:
        """
        Grade: Build Trusted Farmer Network task
        
        Returns: (success, score_multiplier, feedback)
        """
        farmers = metrics.get('unique_farmers', 0)
        avg_trust = metrics.get('avg_farmer_trust', 0)
        orders = metrics.get('completed_orders', 0)
        rejection_rate = metrics.get('rejection_rate', 1.0)
        
        criteria = AgriConnectTasks.TASK_BUILD_NETWORK['success_criteria']
        
        feedbacks = []
        score = 0
        
        # Farmer count check
        if farmers >= criteria['min_farmers']:
            score += 0.3
            feedbacks.append(f"✅ Farmer network established: {farmers} farmers")
        else:
            score += (farmers / criteria['min_farmers']) * 0.3
            feedbacks.append(f"🤝 Farmers: {farmers}/{criteria['min_farmers']}")
        
        # Average trust check
        if avg_trust >= criteria['min_avg_trust']:
            score += 0.3
            feedbacks.append(f"✅ High trust partners: {avg_trust:.1f}/10")
        else:
            score += (avg_trust / criteria['min_avg_trust']) * 0.3
            feedbacks.append(f"⭐ Avg trust: {avg_trust:.1f}/10")
        
        # Completed orders
        if orders >= criteria['min_completed_orders']:
            score += 0.2
            feedbacks.append(f"✅ Relationships established: {orders} orders")
        else:
            score += (orders / criteria['min_completed_orders']) * 0.2
            feedbacks.append(f"📋 Orders: {orders}/{criteria['min_completed_orders']}")
        
        # Rejection rate
        if rejection_rate <= criteria['max_rejection_rate']:
            score += 0.2
            feedbacks.append(f"✅ Low rejection rate: {rejection_rate*100:.0f}%")
        else:
            score = max(0, score - 0.1)
            feedbacks.append(f"⚠️ Rejection rate: {rejection_rate*100:.0f}%")
        
        success = score >= 0.85
        feedback = "\n".join(feedbacks)
        
        return success, score, feedback
    
    @staticmethod
    def grade_reduce_spoilage(metrics: Dict[str, Any]) -> Tuple[bool, float, str]:
        """
        Grade: Reduce Spoilage Rate task
        
        Returns: (success, score_multiplier, feedback)
        """
        spoilage_rate = metrics.get('spoilage_rate', 100)
        orders = metrics.get('completed_orders', 0)
        freshness_avg = metrics.get('avg_freshness', 0)
        acceptance_rate = metrics.get('acceptance_rate', 0)
        
        criteria = AgriConnectTasks.TASK_REDUCE_SPOILAGE['success_criteria']
        
        feedbacks = []
        score = 0
        
        # Spoilage rate check
        if spoilage_rate <= criteria['max_spoilage_rate']:
            score += 0.35
            feedbacks.append(f"✅ Spoilage mastered: {spoilage_rate:.1f}%")
        else:
            score += (1 - min(1, spoilage_rate / 100)) * 0.35
            feedbacks.append(f"📉 Spoilage rate: {spoilage_rate:.1f}%")
        
        # Orders check
        if orders >= criteria['min_orders']:
            score += 0.2
            feedbacks.append(f"✅ Order throughput: {orders} orders")
        else:
            score += (orders / criteria['min_orders']) * 0.2
            feedbacks.append(f"📦 Orders: {orders}/{criteria['min_orders']}")
        
        # Freshness check
        if freshness_avg >= criteria['min_freshness_avg']:
            score += 0.25
            feedbacks.append(f"🌾 High freshness: {freshness_avg:.1f}/10")
        else:
            score += (freshness_avg / criteria['min_freshness_avg']) * 0.25
            feedbacks.append(f"📊 Avg freshness: {freshness_avg:.1f}/10")
        
        # Acceptance rate
        if acceptance_rate >= criteria['min_order_acceptance']:
            score += 0.2
            feedbacks.append(f"✅ Good acceptance: {acceptance_rate*100:.0f}%")
        else:
            score += acceptance_rate * 0.2
            feedbacks.append(f"⏱️ Acceptance rate: {acceptance_rate*100:.0f}%")
        
        success = score >= 0.85
        feedback = "\n".join(feedbacks)
        
        return success, score, feedback
    
    @staticmethod
    def grade_task(task_id: str, metrics: Dict[str, Any], steps_taken: int) -> TaskEvaluation:
        """
        Grade a completed task.
        
        Args:
            task_id: Task identifier
            metrics: Performance metrics dict
            steps_taken: Number of environment steps taken
        
        Returns:
            TaskEvaluation with results
        """
        grader_map = {
            'farmer_maximize_revenue': TaskGrader.grade_maximize_revenue,
            'farmer_reduce_spoilage': TaskGrader.grade_reduce_spoilage,
            'restaurant_build_network': TaskGrader.grade_build_network,
        }
        
        grader = grader_map.get(task_id)
        if not grader:
            return TaskEvaluation(
                task_id=task_id,
                completed=False,
                success=False,
                steps_taken=steps_taken,
                reward_earned=0.0,
                metrics=metrics,
                feedback="Unknown task"
            )
        
        success, score, feedback = grader(metrics)
        task_def = AgriConnectTasks.get_all_tasks()[task_id]
        reward = score * task_def['reward_on_success']
        
        return TaskEvaluation(
            task_id=task_id,
            completed=True,
            success=success,
            steps_taken=steps_taken,
            reward_earned=reward,
            metrics=metrics,
            feedback=feedback
        )
