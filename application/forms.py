from django import forms
from django.contrib.auth.models import User
from common.djangoapps.student.models import UserProfile, CourseEnrollment
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from .models import Franchise, Batch, BatchFeeManagement, StudentFeeManagement, Installment, Payment, InstallmentTemplate


class FranchiseForm(forms.ModelForm):
    class Meta:
        model = Franchise
        fields = ['name', 'coordinator', 'contact_no', 'email', 'location', 'registration_date']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Name'}),
            'coordinator': forms.TextInput(attrs={'placeholder': 'coordinator'}),
            'contact_no': forms.TextInput(attrs={'placeholder': 'Contact '}),
            'email': forms.EmailInput(attrs={'placeholder': 'Email ID'}),
            'location': forms.TextInput(attrs={'placeholder': 'Location'}),
            'registration_date': forms.DateInput(attrs={'type': 'text', 'placeholder': 'Reg Date', 'onfocus': "(this.type='date')", 'onblur': "(this.type='text')"}),
        }


class FranchiseUserRegistrationForm(forms.ModelForm):
    full_name = forms.CharField(max_length=100, label='Full Name', required=True)
    email = forms.EmailField(label='Email', required=True)
    phone = forms.CharField(max_length=20, label='Phone', required=True)
    password = forms.CharField(widget=forms.PasswordInput, label='Password')
    mailing_address = forms.CharField(max_length=255, label='Mailing Address', required=True)

    class Meta:
        model = User
        fields = ['username']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email already exists")
        return email

    def save(self, franchise=None, commit=True):
        user = super().save(commit=False)
        name_parts = self.cleaned_data['full_name'].split(' ', 1)
        user.first_name = name_parts[0]
        user.last_name = name_parts[1] if len(name_parts) > 1 else ''
        user.email = self.cleaned_data['email']
        user.set_password(self.cleaned_data['password'])

        if commit:
            user.save()

            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.name = self.cleaned_data['full_name']
            profile.phone_number = self.cleaned_data['phone']
            profile.mailing_address = self.cleaned_data['mailing_address']
            profile.save()

            if franchise:
                from .models import UserFranchise
                UserFranchise.objects.create(user=user, franchise=franchise)

        return user


class BatchForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = ['batch_no', 'fees', 'course']
        widgets = {
            'batch_no': forms.TextInput(attrs={'placeholder': 'Batch Number'}),
            'fees': forms.NumberInput(attrs={'placeholder': 'Fees'}),
            'course': forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['course'].label_from_instance = lambda obj: obj.display_name or str(obj.id)


class InstallmentTemplateForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'step': '0.01', 'placeholder': 'Amount'})
    )
    repayment_period_days = forms.IntegerField(
        widget=forms.NumberInput(attrs={'placeholder': 'Repayment Period (days)'})
    )


class BatchFeeManagementForm(forms.ModelForm):
    class Meta:
        model = BatchFeeManagement
        fields = ['discount']
        widgets = {
            'discount': forms.NumberInput(attrs={'placeholder': 'Discount Amount'}),
        }


class StudentFeeManagementForm(forms.ModelForm):
    class Meta:
        model = StudentFeeManagement
        fields = ['remaining_amount']


class InstallmentForm(forms.ModelForm):
    class Meta:
        model = Installment
        fields = ['amount', 'due_date', 'status', 'repayment_period_days']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'repayment_period_days': forms.NumberInput(attrs={'min': '0'}),
            'status': forms.Select(choices=Installment.STATUS_CHOICES),
        }


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['payment_date', 'amount']
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
        }


class StudentEditForm(forms.ModelForm):
    phone_number = forms.CharField(max_length=20, label='Phone Number', required=False)
    mailing_address = forms.CharField(max_length=255, label='Mailing Address', required=False)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, 'profile'):
            self.fields['phone_number'].initial = self.instance.profile.phone_number
            self.fields['mailing_address'].initial = self.instance.profile.mailing_address

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.phone_number = self.cleaned_data.get('phone_number')
            profile.mailing_address = self.cleaned_data.get('mailing_address')
            profile.save()
        return user