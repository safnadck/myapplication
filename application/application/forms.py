from django import forms
from django.contrib.auth.models import User
from common.djangoapps.student.models import UserProfile
from .models import Franchise, FranchiseStudentDetails, StudentFeeDetail


class SimpleUserRegistrationForm(forms.ModelForm):
    full_name = forms.CharField(max_length=100, label='Full Name', required=True)
    email = forms.EmailField(label='Email', required=True)
    password = forms.CharField(widget=forms.PasswordInput, label='Password')
    franchise = forms.ModelChoiceField(
        queryset=Franchise.objects.all(),
        required=False,
        label='Franchise'
    )

    class Meta:
        model = User
        fields = ['username']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Email already exists')
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        name_parts = self.cleaned_data['full_name'].split(' ', 1)
        user.first_name = name_parts[0]
        user.last_name = name_parts[1] if len(name_parts) > 1 else ''
        user.email = self.cleaned_data['email']
        user.set_password(self.cleaned_data['password'])

        if commit:
            user.save()
            UserProfile.objects.get_or_create(
                user=user,
                defaults={'name': self.cleaned_data['full_name']}
            )
        return user    
    

class FranchiseRegistrationForm(forms.ModelForm):
    class Meta:
        model = Franchise
        fields = ['name', 'location', 'joining_date']
        widgets = {
            'joining_date': forms.DateInput(attrs={'type': 'date'})
        }


class FranchiseStudentDetailsForm(forms.ModelForm):
    class Meta:
        model = FranchiseStudentDetails
        fields = ['phone_number', 'address', 'duration']        



class StudentFeeDetailForm(forms.ModelForm):
    class Meta:
        model = StudentFeeDetail
        fields = ['total_fees', 'total_installments', 'installments_paid', 'fees_paid']

    def clean(self):
        cleaned_data = super().clean()
        total_fees = cleaned_data.get('total_fees')
        total_installments = cleaned_data.get('total_installments')
        installments_paid = cleaned_data.get('installments_paid')

        if total_installments is not None and installments_paid is not None:
            if installments_paid > total_installments:
                raise forms.ValidationError("Installments paid cannot be greater than total installments.")
        return cleaned_data
