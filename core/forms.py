from django import forms
from authentication.models import User

class UserInviteForm(forms.ModelForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Set Password'}))
    role = forms.ChoiceField(choices=User.ROLE_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    phone_number = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}))
    region = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Region (Optional)'}))

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'role', 'phone_number', 'region']

from django import forms
from .models import Customer
from authentication.models import User

class CustomerModalForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['first_name', 'last_name', 'phone', 'email', 'lead_source', 'assigned_to', 'status', 'address', 'city', 'state', 'pincode', 'notes']
        
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}),
            'lead_source': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Address'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'State'}),
            'pincode': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Pincode'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Internal Notes'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter assigned_to to only show employees/agents, not admins if needed
        self.fields['assigned_to'].queryset = User.objects.filter(is_active=True).order_by('username')
        self.fields['assigned_to'].empty_label = "Unassigned"

from hostinger_data.models import Advertisements, Sliders, Categories

class BannerForm(forms.ModelForm):
    category = forms.ModelChoiceField(
        queryset=Categories.objects.all().order_by('name'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select rounded-pill'}),
        label="Linked Category"
    )

    class Meta:
        model = Advertisements
        fields = ['name', 'content', 'file', 'sequence', 'screen', 'startdate', 'enddate', 'status', 'adminmsg']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control rounded-pill', 'placeholder': 'Banner Name', 'required': 'true'}),
            'content': forms.TextInput(attrs={'class': 'form-control rounded-pill', 'placeholder': 'Content / Link (Optionally auto-filled by Category)'}),
            'file': forms.TextInput(attrs={'class': 'form-control rounded-pill', 'placeholder': 'banners/image.png', 'required': 'true'}),
            'sequence': forms.NumberInput(attrs={'class': 'form-control rounded-pill', 'required': 'true'}),
            'screen': forms.TextInput(attrs={'class': 'form-control rounded-pill', 'placeholder': 'Home / Category / Brand', 'required': 'true'}),
            'startdate': forms.DateInput(attrs={'class': 'form-control rounded-pill', 'type': 'date'}),
            'enddate': forms.DateInput(attrs={'class': 'form-control rounded-pill', 'type': 'date'}),
            'status': forms.Select(choices=((1, 'Active'), (0, 'Inactive')), attrs={'class': 'form-select rounded-pill'}),
            'adminmsg': forms.TextInput(attrs={'class': 'form-control rounded-pill', 'placeholder': 'Optional Admin Message'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Try to pre-select category if content contains a category ID
            try:
                cat_id = int(self.instance.content)
                self.fields['category'].initial = Categories.objects.filter(id=cat_id).first()
            except (ValueError, TypeError):
                pass

    def save(self, commit=True):
        instance = super().save(commit=False)
        category = self.cleaned_data.get('category')
        if category:
            instance.content = str(category.id)
        if commit:
            instance.save()
        return instance

class SliderForm(forms.ModelForm):
    category = forms.ModelChoiceField(
        queryset=Categories.objects.all().order_by('name'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select rounded-pill'}),
        label="Linked Category"
    )

    class Meta:
        model = Sliders
        fields = ['title', 'image', 'screen', 'company_id', 'startdate', 'enddate', 'status']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control rounded-pill', 'placeholder': 'Slider Title', 'required': 'true'}),
            'image': forms.TextInput(attrs={'class': 'form-control rounded-pill', 'placeholder': 'sliders/image.png', 'required': 'true'}),
            'screen': forms.TextInput(attrs={'class': 'form-control rounded-pill', 'placeholder': 'Home / Category / Brand', 'required': 'true'}),
            'company_id': forms.NumberInput(attrs={'class': 'form-control rounded-pill', 'placeholder': 'Company ID (Optionally auto-filled by Category)'}),
            'startdate': forms.DateInput(attrs={'class': 'form-control rounded-pill', 'type': 'date', 'required': 'true'}),
            'enddate': forms.DateInput(attrs={'class': 'form-control rounded-pill', 'type': 'date', 'required': 'true'}),
            'status': forms.Select(choices=((1, 'Active'), (0, 'Inactive')), attrs={'class': 'form-select rounded-pill'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.company_id:
                self.fields['category'].initial = Categories.objects.filter(id=self.instance.company_id).first()

    def save(self, commit=True):
        instance = super().save(commit=False)
        category = self.cleaned_data.get('category')
        if category:
            instance.company_id = category.id
        else:
            if not instance.company_id:
                instance.company_id = 1  # Default fallback
        if commit:
            instance.save()
        return instance