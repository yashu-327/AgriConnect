"""
Django management command to batch update produce states and freshness.
Run with: python manage.py update_produce_states [--limit 100]
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Produce
from core.services import ProduceStateManager


class Command(BaseCommand):
    help = 'Update produce freshness scores, spoilage risk, and states'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of produce items to update (default: all)'
        )
        parser.add_argument(
            '--filter-state',
            type=str,
            default=None,
            help='Only update produce with specific state (fresh, aging, near_expiry, expired, unavailable)'
        )
        parser.add_argument(
            '--dynamic-only',
            action='store_true',
            help='Only update produce with dynamic pricing enabled'
        )
    
    def handle(self, *args, **options):
        limit = options.get('limit')
        filter_state = options.get('filter_state')
        dynamic_only = options.get('dynamic_only')
        
        # Build queryset
        queryset = Produce.objects.all()
        
        if filter_state:
            queryset = queryset.filter(produce_state=filter_state)
        
        if dynamic_only:
            queryset = queryset.filter(is_dynamic_priced=True)
        
        if limit:
            queryset = queryset[:limit]
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting update of {queryset.count()} produce items...')
        )
        
        # Perform batch update
        stats = ProduceStateManager.batch_update_produce_states(
            produce_queryset=queryset,
            limit=None  # We already sliced the queryset
        )
        
        # Display results
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Update complete!\n'
                f'  • Updated: {stats["updated_count"]} items\n'
                f'  • Recently expired: {stats["expired_count"]} items\n'
                f'  • Price recalculated: {stats["price_updated_count"]} items'
            )
        )
