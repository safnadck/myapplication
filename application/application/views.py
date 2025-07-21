from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import connection
from common.djangoapps.student.models import UserProfile
from .forms import SimpleUserRegistrationForm, FranchiseRegistrationForm, FranchiseStudentDetailsForm, StudentFeeDetailForm
from .models import Franchise, UserFranchise , FranchiseStudentDetails, StudentFeeDetail
  

def superuser_required(view_func):
    return user_passes_test(lambda u: u.is_superuser)(view_func)

@login_required
@superuser_required
def user_and_franchise_management(request):
    if request.method == 'POST':
        if 'user_form_submit' in request.POST:
            user_form = SimpleUserRegistrationForm(request.POST)
            franchise_form = FranchiseRegistrationForm()
            if user_form.is_valid():
                user = user_form.save()
                franchise = user_form.cleaned_data.get('franchise')
                if franchise:
                    UserFranchise.objects.create(user=user, franchise=franchise)
                return redirect('application:user_and_franchise_management')

        elif 'franchise_form_submit' in request.POST:
            franchise_form = FranchiseRegistrationForm(request.POST)
            user_form = SimpleUserRegistrationForm()
            if franchise_form.is_valid():
                franchise_form.save()
                return redirect('application:user_and_franchise_management')
    else:
        user_form = SimpleUserRegistrationForm()
        franchise_form = FranchiseRegistrationForm()

    users = []
    for user in User.objects.all():
        try:
            user_franchise = UserFranchise.objects.get(user=user)
            franchise_name = user_franchise.franchise.name
            franchise_id = user_franchise.franchise.id
        except UserFranchise.DoesNotExist:
            franchise_name = "No Franchise"
            franchise_id = None
        
        try:
            profile = UserProfile.objects.get(user=user)
            full_name = profile.name
        except UserProfile.DoesNotExist:
            full_name = f"{user.first_name} {user.last_name}".strip()

        users.append({
            'id': user.id,
            'username': user.username,
            'first_name': full_name,
            'email': user.email,
            'franchises': franchise_name,
            'franchise_id': franchise_id
        })

    franchises = Franchise.objects.all()
    
    return render(request, 'application/user_and_franchise_management.html', {
        'users': users,
        'franchises': franchises,
        'user_form': user_form,
        'franchise_form': franchise_form
    })

@login_required
@superuser_required
def franchise_students(request, franchise_id):
    # View to display students of a franchise and handle new user registration
    franchise = get_object_or_404(Franchise, id=franchise_id)
    user_franchises = UserFranchise.objects.filter(franchise=franchise)

    if request.method == 'POST':
        user_form = SimpleUserRegistrationForm(request.POST)
        if user_form.is_valid():
            user = user_form.save()
            UserFranchise.objects.create(user=user, franchise=franchise)
            return redirect('application:franchise_students', franchise_id=franchise.id)
    else:
        user_form = SimpleUserRegistrationForm(initial={'franchise': franchise})

    students = []
    for user_franchise in user_franchises:
        user = user_franchise.user
        try:
            profile = UserProfile.objects.get(user=user)
            full_name = profile.name
        except UserProfile.DoesNotExist:
            full_name = f"{user.first_name} {user.last_name}".strip()

        # Get additional details from FranchiseStudentDetails
        try:
            details = FranchiseStudentDetails.objects.get(user_franchise=user_franchise)
            phone_number = details.phone_number
            address = details.address
            duration = details.duration
        except FranchiseStudentDetails.DoesNotExist:
            phone_number = None
            address = None
            duration = None

        # Get fee details if available
        try:
            fee_detail = StudentFeeDetail.objects.get(user_franchise=user_franchise)
            pending_fees = fee_detail.pending_fees
        except StudentFeeDetail.DoesNotExist:
            pending_fees = 0.00

        # Fetch enrolled courses for the user from student_courseenrollment table
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT course_id FROM student_courseenrollment
                WHERE user_id = %s AND is_active = 1
            """, [user.id])
            enrolled_courses = [row[0] for row in cursor.fetchall()]

        students.append({
            'id': user.id,
            'username': user.username,
            'full_name': full_name,
            'email': user.email,
            'user_franchise_id': user_franchise.id,
            'phone_number': phone_number,
            'address': address,
            'duration': duration,
            'last_login': user.last_login,
            'pending_fees': pending_fees,  # Added pending fees to student data
            'enrolled_courses': enrolled_courses,  # Added enrolled courses list
        })

    return render(request, 'application/franchise_students.html', {
        'franchise': franchise,
        'students': students,
        'user_form': user_form
    })

@login_required
@superuser_required
def edit_student_details(request, user_franchise_id):
    # View to edit student details
    user_franchise = get_object_or_404(UserFranchise, id=user_franchise_id)
    details, created = FranchiseStudentDetails.objects.get_or_create(user_franchise=user_franchise)
    if request.method == 'POST':
        form = FranchiseStudentDetailsForm(request.POST, instance=details)
        if form.is_valid():
            form.save()
            return redirect('application:franchise_students', franchise_id=user_franchise.franchise.id)
    else:
        form = FranchiseStudentDetailsForm(instance=details)
    return render(request, 'application/edit_student_details.html', {
        'form': form,
        'student': user_franchise.user
    })

@login_required
@superuser_required
def manage_fee_details(request, user_franchise_id):
    """
    View to manage fee details for a student.
    Displays a form to add total fees, total installments, installments paid,
    calculates pending fees, and saves the data.
    """
    user_franchise = get_object_or_404(UserFranchise, id=user_franchise_id)
    fee_detail, created = StudentFeeDetail.objects.get_or_create(user_franchise=user_franchise)

    if request.method == 'POST':
        form = StudentFeeDetailForm(request.POST, instance=fee_detail)
        if form.is_valid():
            form.save()
            # Redirect back to franchise students page after saving
            return redirect('application:franchise_students', franchise_id=user_franchise.franchise.id)
    else:
        form = StudentFeeDetailForm(instance=fee_detail)

    # Calculate pending fees to display in the form
    pending_fees = fee_detail.pending_fees

    franchise_id = user_franchise.franchise.id if user_franchise.franchise else None
    return render(request, 'application/manage_fee_details.html', {
        'form': form,
        'student': user_franchise.user,
        'pending_fees': pending_fees,
        'user_franchise_id': user_franchise_id,
        'franchise_id': franchise_id,
    })


