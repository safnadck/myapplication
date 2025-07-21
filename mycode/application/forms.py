from django import forms
from django.contrib.auth.models import User
from common.djangoapps.student.models import UserProfile
from .models import Franchise, UserFranchise

class SimpleUserRegistrationForm(forms.ModelForm):
    full_name = forms.CharField(max_length=255, required=True)
    email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput)
    franchise = forms.ModelChoiceField(
        queryset=Franchise.objects.all(),
        required=False
    )
    phone_number = forms.CharField(required=False)
    address = forms.CharField(widget=forms.Textarea, required=False)

    class Meta:
        model = User
        fields = ['username']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.set_password(self.cleaned_data['password'])
        
        if commit:
            user.save()
            # Create or update user profile
            UserProfile.objects.update_or_create(
                user=user,
                defaults={'name': self.cleaned_data['full_name']}
            )
            # Create franchise info if franchise was selected
            if self.cleaned_data['franchise']:
                UserFranchise.objects.update_or_create(
                    user=user,
                    defaults={
                        'franchise': self.cleaned_data['franchise'],
                        'phone_number': self.cleaned_data['phone_number'],
                        'address': self.cleaned_data['address']
                    }
                )
        return user

class FranchiseRegistrationForm(forms.ModelForm):
    class Meta:
        model = Franchise
        fields = ['name', 'location', 'joining_date']
        widgets = {
            'joining_date': forms.DateInput(attrs={'type': 'date'})
        }