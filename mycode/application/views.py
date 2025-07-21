from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from common.djangoapps.student.models import UserProfile
from .forms import SimpleUserRegistrationForm, FranchiseRegistrationForm
from .models import Franchise, UserFranchise

@login_required
def user_and_franchise_management(request):
    if request.method == 'POST':
        if 'user_form_submit' in request.POST:
            user_form = SimpleUserRegistrationForm(request.POST)
            if user_form.is_valid():
                user_form.save()
                return redirect('user_and_franchise_management')
        elif 'franchise_form_submit' in request.POST:
            franchise_form = FranchiseRegistrationForm(request.POST)
            if franchise_form.is_valid():
                franchise_form.save()
                return redirect('user_and_franchise_management')
    else:
        user_form = SimpleUserRegistrationForm()
        franchise_form = FranchiseRegistrationForm()

    # Prepare user data with profile and franchise info
    users = []
    for user in User.objects.all():
        try:
            profile = UserProfile.objects.get(user=user)
            full_name = profile.name
        except UserProfile.DoesNotExist:
            full_name = f"{user.first_name} {user.last_name}".strip()

        franchise_name = "No Franchise"
        try:
            user_franchise = UserFranchise.objects.get(user=user)
            if user_franchise.franchise:
                franchise_name = user_franchise.franchise.name
        except UserFranchise.DoesNotExist:
            pass

        users.append({
            'id': user.id,
            'username': user.username,
            'full_name': full_name,
            'email': user.email,
            'franchise': franchise_name
        })

    franchises = Franchise.objects.all()
    
    return render(request, 'user_and_franchise_management.html', {
        'users': users,
        'franchises': franchises,
        'user_form': user_form,
        'franchise_form': franchise_form
    })