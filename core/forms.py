import re
from django import forms
from authentication.models import User

class UserInviteForm(forms.ModelForm):
    first_name = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}))
    last_name = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}))
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Employee ID / Username'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Set Password'}))
    role = forms.ChoiceField(choices=User.ROLE_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    phone_number = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}))
    region = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Region (Optional)'}))

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'password', 'role', 'phone_number', 'region']

from django import forms
from .models import Customer
from authentication.models import User

class CustomerModalForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            'customer_type', 'first_name', 'last_name', 'phone', 'whatsapp_number',
            'email', 'company_name', 'gst_number', 'lead_source', 'assigned_to',
            'status', 'address', 'city', 'state', 'pincode', 'notes'
        ]
        
        widgets = {
            'customer_type': forms.Select(attrs={'class': 'form-select'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name (Optional)'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name (Optional)'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone'}),
            'whatsapp_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'WhatsApp Number (Optional)'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email (Optional)'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Company / Firm Name (Optional)'}),
            'gst_number': forms.TextInput(attrs={'class': 'form-control text-uppercase', 'placeholder': 'GSTIN (Optional)', 'maxlength': '15'}),
            'lead_source': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Address (Optional)'}),
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
        self.fields['first_name'].required = False
        self.fields['last_name'].required = False
        self.fields['address'].required = False
        self.fields['email'].required = False
        self.fields['company_name'].required = False
        self.fields['gst_number'].required = False
        self.fields['whatsapp_number'].required = False

    def clean_last_name(self):
        val = self.cleaned_data.get('last_name')
        if val and str(val).strip().lower() in ('none', 'null', 'undefined', '-', '--'):
            return ""
        return val or ""

    def clean_first_name(self):
        val = self.cleaned_data.get('first_name')
        if val and str(val).strip().lower() in ('none', 'null', 'undefined', '-', '--'):
            return ""
        return val or ""

    def clean_company_name(self):
        val = self.cleaned_data.get('company_name')
        if val and str(val).strip().lower() in ('none', 'null', 'undefined', '-', '--'):
            return ""
        return val or ""

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            import re
            digits = re.sub(r'\D', '', str(phone))
            if len(digits) >= 10:
                phone = digits[-10:]
            else:
                phone = digits
        return phone


class EmployeeCustomerCreateForm(forms.ModelForm):
    CUSTOMER_TYPE_CHOICES = (
        ('buyer', 'Buyer / Contractor'),
        ('seller', 'Customer / Seller / Vendor'),
    )

    customer_type = forms.ChoiceField(
        choices=CUSTOMER_TYPE_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'btn-check'}),
        initial='seller',
        label="Entity / Party Type"
    )

    class Meta:
        model = Customer
        fields = [
            'customer_type',
            'first_name',
            'last_name',
            'phone',
            'whatsapp_number',
            'email',
            'company_name',
            'gst_number',
            'lead_source',
            'status',
            'address',
            'city',
            'state',
            'pincode',
            'country',
            'notes',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Rahul'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Sharma'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 9876543210', 'required': 'true'}),
            'whatsapp_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 9876543210 (or click Same as Phone)'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'e.g. contact@business.com'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Apex Hardware & Sanitary Store'}),
            'gst_number': forms.TextInput(attrs={'class': 'form-control text-uppercase', 'placeholder': 'e.g. 07AAAAA0000A1Z5', 'maxlength': '15'}),
            'lead_source': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Shop/Office Address, Street, Landmark'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. New Delhi'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Delhi', 'list': 'employeeStateList'}),
            'pincode': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 110001', 'maxlength': '10'}),
            'country': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Country', 'value': 'India'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Order capacity, specific requirements, meeting notes, etc.'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = False
        self.fields['last_name'].required = False
        self.fields['email'].required = False
        self.fields['address'].required = False
        self.fields['city'].required = False
        self.fields['state'].required = False
        self.fields['pincode'].required = False
        self.fields['country'].required = False
        self.fields['notes'].required = False
        self.fields['company_name'].required = False
        self.fields['gst_number'].required = False
        self.fields['whatsapp_number'].required = False
        self.fields['phone'].required = True

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if not phone:
            raise forms.ValidationError("Mobile number is required.")
        existing = Customer.objects.filter(phone=phone)
        if self.instance and self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            existing_cust = existing.first()
            owner_info = f" (Already assigned to {existing_cust.assigned_to.username})" if existing_cust.assigned_to else " (Unassigned)"
            raise forms.ValidationError(f"A contact with phone number '{phone}' already exists in CRM{owner_info}.")
        return phone

    def clean_gst_number(self):
        gst = self.cleaned_data.get('gst_number', '')
        if gst:
            gst = gst.strip().upper()
        return gst

    def clean_whatsapp_number(self):
        wa = self.cleaned_data.get('whatsapp_number', '')
        if wa:
            wa = wa.strip()
        return wa

    def clean_last_name(self):
        val = self.cleaned_data.get('last_name')
        if val and str(val).strip().lower() in ('none', 'null', 'undefined', '-', '--'):
            return ""
        return val or ""

    def clean_first_name(self):
        val = self.cleaned_data.get('first_name')
        if val and str(val).strip().lower() in ('none', 'null', 'undefined', '-', '--'):
            return ""
        return val or ""

    def clean_company_name(self):
        val = self.cleaned_data.get('company_name')
        if val and str(val).strip().lower() in ('none', 'null', 'undefined', '-', '--'):
            return ""
        return val or ""

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

class CustomerEditForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            'customer_type',
            'first_name', 'last_name', 'phone', 'whatsapp_number', 'email',
            'company_name', 'gst_number', 'is_gst_verified',
            'address', 'city', 'state', 'pincode', 'country',
            'lead_source', 'status', 'assigned_to', 'notes'
        ]
        widgets = {
            'customer_type': forms.Select(attrs={'class': 'form-select fw-semibold', 'id': 'id_customer_type'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name (Optional)'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name (Optional)'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '10-digit Phone Number'}),
            'whatsapp_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '10-digit WhatsApp Number'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email (Optional)'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Registered Company / Business Name'}),
            'gst_number': forms.TextInput(attrs={'class': 'form-control text-uppercase', 'placeholder': '15-digit GSTIN'}),
            'is_gst_verified': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Office / Factory Address (Optional)'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'State'}),
            'pincode': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Pincode'}),
            'country': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Country'}),
            'lead_source': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Internal notes...'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['assigned_to'].queryset = User.objects.filter(is_active=True).order_by('first_name', 'username')
        self.fields['assigned_to'].empty_label = "Unassigned"
        self.fields['assigned_to'].label_from_instance = lambda obj: f"{obj.get_full_name()} ({obj.username})" if obj.get_full_name() else obj.username
        self.fields['first_name'].required = False
        self.fields['last_name'].required = False
        self.fields['company_name'].required = False
        self.fields['address'].required = False
        self.fields['email'].required = False

        # If logged in user is a regular employee (not admin/superuser), prevent direct reassignment
        if user and getattr(user, 'role', '') == 'employee' and not user.is_superuser:
            if 'assigned_to' in self.fields:
                self.fields['assigned_to'].disabled = True

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '')
        if phone:
            phone = re.sub(r'\D', '', str(phone))
            if len(phone) > 10 and phone.startswith('91'):
                phone = phone[2:]
            if len(phone) > 10 and phone.startswith('0'):
                phone = phone[1:]
        if phone and self.instance.pk:
            exists = Customer.objects.filter(phone=phone).exclude(pk=self.instance.pk).exists()
            if exists:
                raise forms.ValidationError(f"Another customer with phone number {phone} already exists.")
        return phone

    def clean_first_name(self):
        val = self.cleaned_data.get('first_name', '')
        if val and str(val).strip().lower() in ('none', 'null', 'undefined', '-', '--'):
            return ''
        return val.strip() if val else ''

    def clean_last_name(self):
        val = self.cleaned_data.get('last_name', '')
        if val and str(val).strip().lower() in ('none', 'null', 'undefined', '-', '--'):
            return ''
        return val.strip() if val else ''

    def clean_company_name(self):
        val = self.cleaned_data.get('company_name', '')
        if val and str(val).strip().lower() in ('none', 'null', 'undefined', '-', '--'):
            return ''
        return val.strip() if val else ''