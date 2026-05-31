from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count
from django.db.models import Q
from django.http import JsonResponse
from .models import User, Produce, Order, FarmerProfile, RestaurantProfile
from .forms import FarmerRegistrationForm, RestaurantRegistrationForm, ProduceForm, OrderForm
from .services import AnalyticsService, DemandForecastService


def home(request):
    """Landing page"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'index.html')


def register_choice(request):
    """Registration role selection page"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'register_choice.html')


def register_farmer(request):
    """Farmer registration view"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = FarmerRegistrationForm(request.POST)
        if form.is_valid():
            # Check if email already exists
            email = form.cleaned_data['email']
            if User.objects.filter(email=email).exists():
                messages.error(request, 'This email is already registered. Please login instead.')
                return render(request, 'register.html', {'form': form, 'role': 'farmer', 'email_exists': True})
            
            user = form.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, f'Welcome to AgriConnect, {user.first_name}! Your farmer account has been created.')
            return redirect('farmer_dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = FarmerRegistrationForm()
    
    return render(request, 'register.html', {'form': form, 'role': 'farmer'})


def register_restaurant(request):
    """Restaurant registration view"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = RestaurantRegistrationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            if User.objects.filter(email=email).exists():
                messages.error(request, 'This email is already registered. Please login instead.')
                return render(request, 'register.html', {'form': form, 'role': 'restaurant', 'email_exists': True})
            
            user = form.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, f'Welcome to AgriConnect! Your restaurant account has been created.')
            return redirect('restaurant_dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = RestaurantRegistrationForm()
    
    return render(request, 'register.html', {'form': form, 'role': 'restaurant'})


def user_login(request):
    """Login view for both farmers and restaurants"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    active_role = 'farmer'  # Default role to display
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        role = request.POST.get('role', 'farmer')
        active_role = role  # Remember which form was submitted
        
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            if user.role == role:
                login(request, user)
                messages.success(request, f'Welcome back, {user.first_name}!')
                return redirect('dashboard')
            else:
                messages.error(request, f'This account is registered as a {user.get_role_display()}, not a {role}.')
        else:
            messages.error(request, 'Invalid email or password. Please try again.')
    
    return render(request, 'login.html', {'active_role': active_role})


def user_logout(request):
    """Logout view"""
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('home')


@login_required
def dashboard(request):
    """Redirect to appropriate dashboard based on user role"""
    if request.user.is_farmer():
        return redirect('farmer_dashboard')
    elif request.user.is_restaurant():
        return redirect('restaurant_dashboard')
    return redirect('home')


def _get_farmer_dashboard_context(user, home_mode=False):
    """Build shared context for farmer pages."""
    produce_listings = Produce.objects.filter(farmer=user)
    incoming_orders = Order.objects.filter(farmer=user).select_related('restaurant', 'produce')
    analytics = AnalyticsService.get_farmer_dashboard_analytics(user)
    forecast_highlights = DemandForecastService.get_produce_trend(limit=3)

    return {
        'produce_listings': produce_listings,
        'incoming_orders': incoming_orders,
        'total_produce': produce_listings.count(),
        'available_produce': produce_listings.filter(status='available').count(),
        'pending_orders': incoming_orders.filter(status='pending').count(),
        'form': ProduceForm(),
        'analytics': analytics,
        'forecast_highlights': forecast_highlights,
        'home_mode': home_mode,
    }


@login_required
def farmer_home(request):
    """Home page for logged-in farmer users"""
    if request.user.is_farmer():
        return render(request, 'farmer_dashboard.html', _get_farmer_dashboard_context(request.user, home_mode=True))
    if request.user.is_restaurant():
        return redirect('restaurant_dashboard')
    return redirect('home')


@login_required
def restaurant_home(request):
    """Home page for logged-in restaurant users"""
    if request.user.is_restaurant():
        return render(request, 'restaurant_dashboard.html', _get_restaurant_dashboard_context(request, request.user, home_mode=True))
    if request.user.is_farmer():
        return redirect('farmer_dashboard')
    return redirect('home')


def _get_restaurant_dashboard_context(request, user, home_mode=False):
    """Build shared context for restaurant pages."""
    available_produce = Produce.objects.filter(
        status__in=['available', 'pending']
    ).select_related('farmer', 'farmer__farmer_profile')

    search_query = request.GET.get('search', '').strip()
    location_filter = request.GET.get('location', '').strip()
    category_filter = request.GET.get('category', '').strip()
    status_filter = request.GET.get('status', '').strip()
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()
    sort_by = request.GET.get('sort_by', 'newest').strip()

    if search_query:
        available_produce = available_produce.filter(
            Q(name__icontains=search_query)
            | Q(farmer__username__icontains=search_query)
            | Q(farmer__farmer_profile__location__icontains=search_query)
        )

    if location_filter:
        available_produce = available_produce.filter(farmer__farmer_profile__location=location_filter)

    if category_filter in dict(Produce.CATEGORY_CHOICES):
        available_produce = available_produce.filter(category=category_filter)

    if status_filter in ['available', 'pending', 'sold']:
        available_produce = available_produce.filter(status=status_filter)

    if min_price:
        try:
            available_produce = available_produce.filter(price_per_kg__gte=min_price)
        except (ValueError, TypeError):
            pass

    if max_price:
        try:
            available_produce = available_produce.filter(price_per_kg__lte=max_price)
        except (ValueError, TypeError):
            pass

    sort_map = {
        'newest': '-created_at',
        'price_low': 'price_per_kg',
        'price_high': '-price_per_kg',
        'name_asc': 'name',
    }
    available_produce = available_produce.order_by(sort_map.get(sort_by, '-created_at'))

    location_options = list(
        User.objects.filter(role='farmer')
        .values_list('farmer_profile__location', flat=True)
        .exclude(farmer_profile__location__isnull=True)
        .exclude(farmer_profile__location__exact='')
        .distinct()
        .order_by('farmer_profile__location')
    )
    category_options = Produce.CATEGORY_CHOICES

    my_orders = Order.objects.filter(restaurant=user).select_related('farmer', 'produce')
    analytics = AnalyticsService.get_restaurant_dashboard_analytics(user)

    from .services import RecommendationService
    recommendations = RecommendationService.get_best_produce_for_restaurant(user, limit=5)

    return {
        'available_produce': available_produce,
        'my_orders': my_orders,
        'total_farmers': User.objects.filter(role='farmer').count(),
        'total_produce': available_produce.count(),
        'pending_orders': my_orders.filter(status='pending').count(),
        'analytics': analytics,
        'recommendations': recommendations,
        'home_mode': home_mode,
        'location_options': location_options,
        'category_options': category_options,
        'filters': {
            'search': search_query,
            'location': location_filter,
            'category': category_filter,
            'status': status_filter,
            'min_price': min_price,
            'max_price': max_price,
            'sort_by': sort_by,
        },
    }


@login_required
def farmer_dashboard(request):
    """Farmer dashboard view"""
    if not request.user.is_farmer():
        messages.error(request, 'Access denied. This page is for farmers only.')
        return redirect('dashboard')

    return render(request, 'farmer_dashboard.html', _get_farmer_dashboard_context(request.user))


@login_required
def add_produce(request):
    """Add new produce listing"""
    if not request.user.is_farmer():
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = ProduceForm(request.POST, request.FILES)
        if form.is_valid():
            produce = form.save(commit=False)
            produce.farmer = request.user
            produce.save()
            messages.success(request, f'Successfully added {produce.name} to your listings!')
        else:
            messages.error(request, 'Please correct the errors in the form.')
    
    return redirect('farmer_dashboard')


@login_required
def update_order_status(request, order_id, status):
    """Accept or reject an order"""
    if not request.user.is_farmer():
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    order = get_object_or_404(Order, id=order_id, farmer=request.user)
    
    if status in ['accepted', 'rejected']:
        order.status = status
        order.save()
        
        if status == 'accepted':
            # Update produce quantity
            produce = order.produce
            produce.quantity -= order.quantity_requested
            produce.update_status()
            messages.success(request, f'Order #{order.id} has been accepted!')
        else:
            messages.info(request, f'Order #{order.id} has been rejected.')
    
    return redirect('farmer_dashboard')


@login_required
def restaurant_dashboard(request):
    """Restaurant dashboard view"""
    if not request.user.is_restaurant():
        messages.error(request, 'Access denied. This page is for restaurants only.')
        return redirect('dashboard')

    return render(request, 'restaurant_dashboard.html', _get_restaurant_dashboard_context(request, request.user))


@login_required
def request_supply(request, produce_id):
    """Request supply from a farmer"""
    if not request.user.is_restaurant():
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    
    produce = get_object_or_404(Produce, id=produce_id)
    
    if request.method == 'POST':
        quantity = request.POST.get('quantity', '').strip()
        
        # Handle empty quantity
        if not quantity:
            messages.error(request, 'Please enter a quantity.')
            return redirect('restaurant_dashboard')
        
        try:
            # Replace comma with period for decimal parsing
            quantity = quantity.replace(',', '.')
            quantity = float(quantity)
            
            if quantity <= 0:
                messages.error(request, 'Quantity must be greater than zero.')
                return redirect('restaurant_dashboard')
            
            if quantity > float(produce.quantity):
                messages.error(request, f'Requested quantity exceeds available stock ({produce.quantity} kg).')
                return redirect('restaurant_dashboard')
            
            # Create order
            from decimal import Decimal
            order = Order.objects.create(
                restaurant=request.user,
                farmer=produce.farmer,
                produce=produce,
                quantity_requested=Decimal(str(quantity))
            )
            messages.success(request, f'✅ Supply request sent to {produce.farmer.first_name} for {quantity} kg of {produce.name}!')
        except (ValueError, TypeError) as e:
            messages.error(request, f'Please enter a valid number for quantity.')
    
    return redirect('restaurant_dashboard')


def check_email(request):
    """AJAX endpoint to check if email already exists"""
    email = request.GET.get('email', '')
    exists = User.objects.filter(email=email).exists()
    return JsonResponse({'exists': exists})
