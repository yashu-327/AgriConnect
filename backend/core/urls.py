from django.urls import path
from . import views

urlpatterns = [
    # Home
    path('', views.home, name='home'),
    path('farmer/home/', views.farmer_home, name='farmer_home'),
    path('restaurant/home/', views.restaurant_home, name='restaurant_home'),
    
    # Authentication
    path('register/', views.register_choice, name='register'),
    path('register/farmer/', views.register_farmer, name='register_farmer'),
    path('register/restaurant/', views.register_restaurant, name='register_restaurant'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    path('farmer/dashboard/', views.farmer_dashboard, name='farmer_dashboard'),
    path('restaurant/dashboard/', views.restaurant_dashboard, name='restaurant_dashboard'),
    
    # Farmer actions
    path('farmer/add-produce/', views.add_produce, name='add_produce'),
    path('farmer/order/<int:order_id>/<str:status>/', views.update_order_status, name='update_order_status'),
    
    # Restaurant actions
    path('restaurant/request/<int:produce_id>/', views.request_supply, name='request_supply'),
    
    # API
    path('api/check-email/', views.check_email, name='check_email'),
]
