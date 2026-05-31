from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, FarmerProfile, RestaurantProfile, Produce, Order, Rating


class FarmerRegistrationForm(UserCreationForm):
    """Registration form for Farmers"""
    first_name = forms.CharField(max_length=100, required=True)
    last_name = forms.CharField(max_length=100, required=True)
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=15, required=True)
    farm_name = forms.CharField(max_length=200, required=False)
    location = forms.CharField(max_length=300, required=True)
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'password1', 'password2']
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']  # Use email as username
        user.email = self.cleaned_data['email']
        user.role = 'farmer'
        user.phone = self.cleaned_data['phone']
        
        if commit:
            user.save()
            # Create farmer profile
            FarmerProfile.objects.create(
                user=user,
                farm_name=self.cleaned_data.get('farm_name', ''),
                location=self.cleaned_data['location']
            )
        return user


class RestaurantRegistrationForm(UserCreationForm):
    """Registration form for Restaurants"""
    restaurant_name = forms.CharField(max_length=200, required=True)
    owner_name = forms.CharField(max_length=200, required=True)
    restaurant_type = forms.ChoiceField(choices=RestaurantProfile.RESTAURANT_TYPES, required=True)
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=15, required=True)
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=True)
    gst_number = forms.CharField(max_length=20, required=False)
    
    class Meta:
        model = User
        fields = ['email', 'phone', 'password1', 'password2']
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['owner_name']
        user.role = 'restaurant'
        user.phone = self.cleaned_data['phone']
        
        if commit:
            user.save()
            # Create restaurant profile
            RestaurantProfile.objects.create(
                user=user,
                restaurant_name=self.cleaned_data['restaurant_name'],
                restaurant_type=self.cleaned_data['restaurant_type'],
                address=self.cleaned_data['address'],
                gst_number=self.cleaned_data.get('gst_number', '')
            )
        return user


class ProduceForm(forms.ModelForm):
    """Form for adding/editing produce"""
    class Meta:
        model = Produce
        fields = ['name', 'category', 'crop_image', 'quantity', 'price_per_kg', 'availability_date', 'contact_number']
        widgets = {
            'availability_date': forms.DateInput(attrs={'type': 'date'}),
            'name': forms.TextInput(attrs={'placeholder': 'e.g., Tomatoes'}),
            'category': forms.Select(),
            'quantity': forms.NumberInput(attrs={'placeholder': 'e.g., 100', 'min': '1'}),
            'price_per_kg': forms.NumberInput(attrs={'placeholder': 'e.g., 50', 'min': '1', 'step': '0.01'}),
            'contact_number': forms.TextInput(attrs={'placeholder': 'e.g., +91 98765 43210'}),
        }


class OrderForm(forms.ModelForm):
    """Form for placing orders"""
    class Meta:
        model = Order
        fields = ['quantity_requested']
        widgets = {
            'quantity_requested': forms.NumberInput(attrs={'placeholder': 'Enter quantity in kg', 'min': '1'}),
        }


class RatingForm(forms.ModelForm):
    """Form for rating users (farmers or restaurants) after completed transactions"""
    
    SCORE_CHOICES = [
        (5, '⭐⭐⭐⭐⭐ Excellent'),
        (4, '⭐⭐⭐⭐ Very Good'),
        (3, '⭐⭐⭐ Good'),
        (2, '⭐⭐ Fair'),
        (1, '⭐ Poor'),
    ]
    
    score = forms.ChoiceField(
        choices=SCORE_CHOICES,
        widget=forms.RadioSelect,
        label='Overall Rating'
    )
    
    quality_score = forms.ChoiceField(
        choices=SCORE_CHOICES,
        widget=forms.RadioSelect,
        required=False,
        label='Quality of Product/Service'
    )
    
    timeliness_score = forms.ChoiceField(
        choices=SCORE_CHOICES,
        widget=forms.RadioSelect,
        required=False,
        label='Timeliness & Delivery'
    )
    
    communication_score = forms.ChoiceField(
        choices=SCORE_CHOICES,
        widget=forms.RadioSelect,
        required=False,
        label='Communication & Responsiveness'
    )
    
    class Meta:
        model = Rating
        fields = ['score', 'quality_score', 'timeliness_score', 'communication_score', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={
                'placeholder': 'Share your experience... (optional)',
                'rows': 4,
                'class': 'form-control'
            }),
        }
