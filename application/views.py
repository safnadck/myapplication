from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.db import models
from .forms import FranchiseForm, BatchForm, FranchiseUserRegistrationForm, BatchFeeManagementForm, StudentFeeManagementForm, InstallmentForm, EditInstallmentForm, PaymentForm, StudentEditForm
from .models import Franchise, UserFranchise, Batch, BatchFeeManagement, StudentFeeManagement, Installment, InstallmentTemplate
from django.contrib.auth.decorators import login_required, user_passes_test
from collections import defaultdict
from django.db.models import Count
from django.urls import reverse
from django.forms import modelformset_factory
from datetime import timedelta
from django.utils import timezone
from django.db import OperationalError, transaction
from time import sleep

from common.djangoapps.student.models import UserProfile

from common.djangoapps.student.models import CourseEnrollment
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview


def superuser_required(view_func):
    return user_passes_test(lambda u: u.is_superuser)(view_func)


@login_required
@superuser_required
def homepage(request):
    total_franchises = Franchise.objects.count()
    total_students = User.objects.count()
    total_courses = CourseOverview.objects.count()

    return render(request, 'application/homepage.html', {
        'total_franchises': total_franchises,
        'total_students': total_students,
        'total_courses': total_courses
    })


@login_required
@superuser_required
def fee_reminders(request):
    if request.method == 'POST':
        installment_id = request.POST.get('installment_id')
        if installment_id:
            try:
                installment = Installment.objects.select_related(
                    'student_fee_management__user_franchise__user',
                    'student_fee_management__user_franchise__batch'
                ).get(id=installment_id)
                user = installment.student_fee_management.user_franchise.user
                batch = installment.student_fee_management.user_franchise.batch
                course_id = batch.course.id if batch and batch.course else None
                if course_id:
                    if CourseEnrollment.is_enrolled(user, course_id):
                        CourseEnrollment.unenroll(user, course_id)
            except Installment.DoesNotExist:
                pass
        return redirect('application:fee_reminders')

    today = timezone.now().date()
    three_days_later = today + timedelta(days=3)

    upcoming_installments = Installment.objects.filter(
        due_date__gte=today,
        due_date__lte=three_days_later,
        status='pending'
    ).select_related('student_fee_management__user_franchise__user', 'student_fee_management__user_franchise__batch')

    overdue_installments = Installment.objects.filter(
        due_date__lt=today
    ).exclude(status='paid').select_related('student_fee_management__user_franchise__user', 'student_fee_management__user_franchise__batch')

    overdue_data = []
    for installment in overdue_installments:
        user = installment.student_fee_management.user_franchise.user
        batch = installment.student_fee_management.user_franchise.batch
        course_id = batch.course.id if batch and batch.course else None
        is_enrolled = False
        if course_id:
            is_enrolled = CourseEnrollment.is_enrolled(user, course_id)
        overdue_data.append({
            'installment': installment,
            'is_enrolled': is_enrolled
        })

    return render(request, 'application/fee_reminders.html', {
        'upcoming_installments': upcoming_installments,
        'overdue_data': overdue_data,
    })


@login_required
@superuser_required
def inactive_users(request):
    # Get users who haven't logged in for the last 2 days
    two_days_ago = timezone.now() - timedelta(days=2)
    inactive_users = User.objects.filter(
        models.Q(last_login__isnull=True) | models.Q(last_login__lt=two_days_ago)
    ).order_by('last_login')

    # Calculate days since last login for each user
    user_data = []
    now = timezone.now()
    for user in inactive_users:
        if user.last_login:
            days_inactive = (now - user.last_login).days
        else:
            days_inactive = None  # Never logged in

        # Try to get phone number from user profile
        try:
            profile = UserProfile.objects.get(user=user)
            phone_number = profile.phone_number
        except UserProfile.DoesNotExist:
            phone_number = None

        # Get batch from UserFranchise
        try:
            user_franchise = UserFranchise.objects.get(user=user)
            batch = user_franchise.batch
        except UserFranchise.DoesNotExist:
            batch = None

        user_data.append({
            'user': user,
            'days_inactive': days_inactive,
            'phone_number': phone_number,
            'batch': batch,
        })

    return render(request, 'application/inactive_users.html', {
        'user_data': user_data,
        'two_days_ago': two_days_ago,
    })


@login_required
@superuser_required
def franchise_list(request):
    franchises = Franchise.objects.all()
    return render(request, 'application/franchise_management.html', {'franchises': franchises})


@login_required
@superuser_required
def franchise_register(request):
    if request.method == "POST":
        form = FranchiseForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('application:franchise_list')
    else:
        form = FranchiseForm()
    
    return render(request, 'application/franchise_register.html', {'form': form})


@login_required
@superuser_required
def franchise_edit(request, pk):
    franchise = get_object_or_404(Franchise, pk=pk)
    
    if request.method == "POST":
        form = FranchiseForm(request.POST, instance=franchise)
        if form.is_valid():
            form.save()
            return redirect('application:franchise_list')
    else:
        form = FranchiseForm(instance=franchise)
    
    return render(request, 'application/franchise_edit.html', {'form': form, 'franchise': franchise})


@login_required
@superuser_required
def franchise_report(request, pk):
    franchise = get_object_or_404(Franchise, pk=pk)

    student_ids = list(
        UserFranchise.objects.filter(franchise=franchise).values_list('user_id', flat=True)
    )
    enrollments = CourseEnrollment.objects.filter(
        user_id__in=student_ids,
        is_active=True
    )

    course_counts = (
        enrollments.values('course_id')
        .annotate(student_count=Count('user_id', distinct=True))
    )
    course_student_map = {row['course_id']: row['student_count'] for row in course_counts}
    courses = list(CourseOverview.objects.filter(id__in=course_student_map.keys()))

    for course in courses:
        course.student_count = course_student_map.get(course.id, 0)

    users = list(User.objects.filter(id__in=student_ids).order_by('username'))

    batches = Batch.objects.filter(franchise=franchise).select_related('course')

    return render(request, 'application/franchise_report.html', {
        'franchise': franchise,
        'courses': courses,
        'users': users,
        'batches': batches,
    })


@login_required
@superuser_required
def batch_create(request, pk):
    franchise = get_object_or_404(Franchise, pk=pk)

    if request.method == "POST":
        form = BatchForm(request.POST)
        if form.is_valid():
            batch = form.save(commit=False)
            batch.franchise = franchise
            batch.save()
            
            # Create BatchFeeManagement automatically
            BatchFeeManagement.objects.create(batch=batch)
            
            return redirect('application:franchise_report', pk=franchise.pk)
    else:
        form = BatchForm()

    return render(request, 'application/batch_create.html', {
        'form': form,
        'franchise': franchise,
    })


@login_required
@superuser_required
def batch_students(request, franchise_pk, batch_pk):
    franchise = get_object_or_404(Franchise, pk=franchise_pk)
    batch = get_object_or_404(Batch, pk=batch_pk, franchise=franchise)

    user_franchises = UserFranchise.objects.filter(franchise=franchise, batch=batch).select_related('user')
    users = [uf.user for uf in user_franchises]

    return render(request, 'application/batch_students.html', {
        'franchise': franchise,
        'batch': batch,
        'users': users,
    })


@login_required
@superuser_required
def student_detail(request, franchise_pk, batch_pk, user_pk):
    franchise = get_object_or_404(Franchise, pk=franchise_pk)
    batch = get_object_or_404(Batch, pk=batch_pk, franchise=franchise)
    user = get_object_or_404(User, pk=user_pk)

    user_franchise = get_object_or_404(UserFranchise, user=user, franchise=franchise, batch=batch)

    fee_management = get_object_or_404(BatchFeeManagement, batch=batch)
    student_fee, created = StudentFeeManagement.objects.get_or_create(
        user_franchise=user_franchise,
        defaults={'batch_fee_management': fee_management}
    )

    enrollment = CourseEnrollment.objects.get(user=user, course_id=batch.course.id)
    registration_date = enrollment.created.date()

    if not Installment.objects.filter(student_fee_management=student_fee).exists():
        templates = InstallmentTemplate.objects.filter(batch_fee_management=fee_management).order_by('id')
        cumulative_days = 0
        for template in templates:
            cumulative_days += template.repayment_period_days
            due_date = registration_date + timedelta(days=cumulative_days)

            Installment.objects.create(
                student_fee_management=student_fee,
                due_date=due_date,
                amount=template.amount,
                repayment_period_days=template.repayment_period_days
            )

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'enroll':
            if not CourseEnrollment.is_enrolled(user, batch.course.id):
                CourseEnrollment.enroll(user, batch.course.id)
        elif action == 'unenroll':
            if CourseEnrollment.is_enrolled(user, batch.course.id):
                CourseEnrollment.unenroll(user, batch.course.id)
        return redirect('application:student_detail', franchise_pk=franchise.pk, batch_pk=batch.pk, user_pk=user.pk)

    existing_installments = Installment.objects.filter(student_fee_management=student_fee).order_by('due_date')
    installments = [{'installment': inst} for inst in existing_installments]

    is_enrolled = CourseEnrollment.is_enrolled(user, batch.course.id)

    return render(request, 'application/student_detail.html', {
        'franchise': franchise,
        'batch': batch,
        'user': user,
        'user_franchise': user_franchise,
        'fee_management': fee_management,
        'student_fee': student_fee,
        'installments': installments,
        'is_enrolled': is_enrolled,
    })


@login_required
@superuser_required
def edit_student_details(request, franchise_pk, batch_pk, user_pk):
    franchise = get_object_or_404(Franchise, pk=franchise_pk)
    batch = get_object_or_404(Batch, pk=batch_pk, franchise=franchise)
    user = get_object_or_404(User, pk=user_pk)

    if request.method == "POST":
        form = StudentEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            return redirect('application:student_detail', franchise_pk=franchise.pk, batch_pk=batch.pk, user_pk=user.pk)
    else:
        form = StudentEditForm(instance=user)

    return render(request, 'application/edit_student_details.html', {
        'form': form,
        'franchise': franchise,
        'batch': batch,
        'user': user,
    })


@login_required
@superuser_required
def batch_user_register(request, franchise_pk, batch_pk):
    franchise = get_object_or_404(Franchise, pk=franchise_pk)
    batch = get_object_or_404(Batch, pk=batch_pk, franchise=franchise)

    if request.method == "POST":
        form = FranchiseUserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(franchise=franchise, commit=True)
            CourseEnrollment.enroll(user, batch.course.id)
            
            user_franchise = UserFranchise.objects.get(user=user, franchise=franchise)
            user_franchise.batch = batch
            user_franchise.save()
            
            return redirect('application:batch_students', franchise_pk=franchise.pk, batch_pk=batch.pk)
    else:
        form = FranchiseUserRegistrationForm()

    return render(request, 'application/user_register_course.html', {
        'form': form,
        'franchise': franchise,
        'batch': batch,
    })


@login_required
@superuser_required
def batch_fee_management(request, franchise_pk, batch_pk):
    franchise = get_object_or_404(Franchise, pk=franchise_pk)
    batch = get_object_or_404(Batch, pk=batch_pk, franchise=franchise)

    fee_management, created = BatchFeeManagement.objects.get_or_create(batch=batch)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "save_discount":
            form = BatchFeeManagementForm(request.POST, instance=fee_management)
            if form.is_valid():
                form.save()
            return redirect('application:batch_fee_management', franchise_pk=franchise.pk, batch_pk=batch.pk)

        elif action == "save_installments":
            InstallmentTemplate.objects.filter(batch_fee_management=fee_management).delete()

            installment_count = 0
            while f'installment_amount_{installment_count + 1}' in request.POST:
                installment_count += 1
                amount = request.POST.get(f'installment_amount_{installment_count}')
                period = request.POST.get(f'repayment_period_{installment_count}')
                if amount and period:
                    InstallmentTemplate.objects.create(
                        batch_fee_management=fee_management,
                        amount=amount,
                        repayment_period_days=period
                    )
            return redirect('application:batch_fee_management', franchise_pk=franchise.pk, batch_pk=batch.pk)

    else:
        form = BatchFeeManagementForm(instance=fee_management)

    installments = InstallmentTemplate.objects.filter(batch_fee_management=fee_management)

    return render(request, 'application/batch_fee_management.html', {
        'form': form,
        'franchise': franchise,
        'batch': batch,
        'fee_management': fee_management,
        'installments': installments,
    })


@login_required
@superuser_required
def student_fee_management(request, franchise_pk, batch_pk, user_pk):
    franchise = get_object_or_404(Franchise, pk=franchise_pk)
    batch = get_object_or_404(Batch, pk=batch_pk, franchise=franchise)
    user = get_object_or_404(User, pk=user_pk)

    fee_management = get_object_or_404(BatchFeeManagement, batch=batch)
    user_franchise = get_object_or_404(UserFranchise, user=user, franchise=franchise, batch=batch)

    student_fee, created = StudentFeeManagement.objects.get_or_create(
        user_franchise=user_franchise,
        defaults={'batch_fee_management': fee_management}
    )

    enrollment = CourseEnrollment.objects.get(user=user, course_id=batch.course.id)
    registration_date = enrollment.created.date()

    if request.method == "POST":
        existing_installments = Installment.objects.filter(student_fee_management=student_fee).order_by('due_date')
        # Validate that payments are marked in order and paid installments cannot be changed
        error_message = None
        last_paid_index = -1
        for i, installment in enumerate(existing_installments):
            status_key = f'status_{installment.id}'
            payed_amount_key = f'payed_amount_{installment.id}'
            if status_key in request.POST and payed_amount_key in request.POST:
                new_status = request.POST[status_key]
                try:
                    new_payed_amount = float(request.POST[payed_amount_key])
                except ValueError:
                    error_message = "Invalid payed amount."
                    break

                if new_status not in ['pending', 'paid', 'overdue']:
                    error_message = "Invalid status value."
                    break

                if new_payed_amount < 0:
                    error_message = "Payed amount must be greater than or equal to 0."
                    break

                # New validation: if status is paid, payed amount must be > 0
                if new_status == 'paid' and new_payed_amount <= 0:
                    error_message = "Payed amount must be greater than zero to mark as paid."
                    break

                # If installment is already paid, status cannot be changed
                if installment.status == 'paid' and new_status != 'paid':
                    error_message = "Paid installments cannot be changed."
                    break

                # Enforce order: can only mark this installment as paid if all previous are paid
                if new_status == 'paid':
                    if i > 0 and existing_installments[i-1].status != 'paid':
                        error_message = "Payments must be marked in order."
                        break
                    last_paid_index = i

        if error_message:
            from django.contrib import messages
            messages.error(request, error_message)
        else:
            # Save changes if no errors
            for i, installment in enumerate(existing_installments):
                status_key = f'status_{installment.id}'
                payed_amount_key = f'payed_amount_{installment.id}'
                if status_key in request.POST and payed_amount_key in request.POST:
                    new_status = request.POST[status_key]
                    try:
                        new_payed_amount = float(request.POST[payed_amount_key])
                    except ValueError:
                        new_payed_amount = 0

                    if new_status in ['pending', 'paid', 'overdue']:
                        if installment.status != 'paid':  # Only update if not already paid
                            installment.status = new_status
                            installment.payed_amount = new_payed_amount
                            if new_status == 'paid' and not installment.payment_date:
                                installment.payment_date = timezone.now().date()
                            elif new_status != 'paid':
                                installment.payment_date = None
                            installment.save()

            total_paid = sum(inst.payed_amount for inst in Installment.objects.filter(student_fee_management=student_fee))
            student_fee.remaining_amount = fee_management.remaining_amount - total_paid
            student_fee.save()

        return redirect('application:student_fee_management', franchise_pk=franchise.pk, batch_pk=batch.pk, user_pk=user.pk)

    existing_installments = Installment.objects.filter(student_fee_management=student_fee).order_by('due_date')
    installments = [{'installment': installment, 'repayment_period_days': installment.repayment_period_days} for installment in existing_installments]

    total_paid = sum(installment.payed_amount for installment in existing_installments)
    total_pending = sum(installment.amount - installment.payed_amount for installment in existing_installments)

    return render(request, 'application/student_fee_management.html', {
        'franchise': franchise,
        'batch': batch,
        'user': user,
        'fee_management': fee_management,
        'installments': installments,
        'total_paid': total_paid,
        'total_pending': total_pending,
        'registration_date': registration_date,
    })




from django.contrib import messages
from django.forms import modelformset_factory

@login_required
@superuser_required
def edit_installment_setup(request, franchise_pk, batch_pk, user_pk):
    franchise = get_object_or_404(Franchise, pk=franchise_pk)
    batch = get_object_or_404(Batch, pk=batch_pk, franchise=franchise)
    user = get_object_or_404(User, pk=user_pk)

    fee_management = get_object_or_404(BatchFeeManagement, batch=batch)
    user_franchise = get_object_or_404(UserFranchise, user=user, franchise=franchise, batch=batch)
    student_fee = get_object_or_404(StudentFeeManagement, user_franchise=user_franchise)

    # Get registration date
    enrollment = CourseEnrollment.objects.get(user=user, course_id=batch.course.id)
    registration_date = enrollment.created.date()

    # Define the formset - only include editable fields
    EditInstallmentFormSet = modelformset_factory(
        Installment, 
        form=EditInstallmentForm, 
        extra=0, 
        can_delete=True,
        fields=['amount', 'repayment_period_days']  # Only include editable fields
    )

    if request.method == "POST":
        formset = EditInstallmentFormSet(
            request.POST, 
            queryset=Installment.objects.filter(student_fee_management=student_fee)
        )
        
        if formset.is_valid():
            try:
                with transaction.atomic():
                    instances = formset.save(commit=False)
                    
                    # Process deleted instances
                    for obj in formset.deleted_objects:
                        obj.delete()
                    
                    # First pass: Save all instances with temporary due_date
                    for instance in instances:
                        if not instance.pk:  # New instance
                            instance.student_fee_management = student_fee
                            instance.status = 'pending'
                            # Set a temporary due_date to avoid null constraint
                            instance.due_date = timezone.now().date()
                        instance.save()
                    
                    # Now recalculate due dates for all installments properly
                    all_installments = Installment.objects.filter(
                        student_fee_management=student_fee
                    ).order_by('id')
                    
                    cumulative_days = 0
                    for installment in all_installments:
                        cumulative_days += installment.repayment_period_days
                        installment.due_date = registration_date + timedelta(days=cumulative_days)
                        installment.save()
                    
                    # Calculate total installment amount
                    total_installments = sum(
                        inst.amount for inst in Installment.objects.filter(
                            student_fee_management=student_fee
                        )
                    )
                    
                    # Calculate amount to be added to match remaining amount
                    amount_to_add = fee_management.remaining_amount - total_installments
                    
                    messages.success(request, f'Installments updated successfully! Amount to add: ₹{amount_to_add:.2f}')
                    return redirect('application:student_fee_management', 
                                  franchise_pk=franchise.pk, 
                                  batch_pk=batch.pk, 
                                  user_pk=user.pk)
                    
            except Exception as e:
                messages.error(request, f'Error updating installments: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    
    else:
        formset = EditInstallmentFormSet(
            queryset=Installment.objects.filter(student_fee_management=student_fee)
        )

    # Calculate current totals for display
    current_installments = Installment.objects.filter(student_fee_management=student_fee)
    total_installment_amount = sum(inst.amount for inst in current_installments)
    amount_to_add = fee_management.remaining_amount - total_installment_amount
    amount_to_add_absolute = abs(amount_to_add)  # Calculate absolute value for template

    return render(request, 'application/edit_installment_setup.html', {
        'franchise': franchise,
        'batch': batch,
        'user': user,
        'formset': formset,
        'student_fee': student_fee,
        'fee_management': fee_management,
        'enrollment': enrollment,
        'total_installment_amount': total_installment_amount,
        'amount_to_add': amount_to_add,
        'amount_to_add_absolute': amount_to_add_absolute,  # Pass absolute value to template
    })


@login_required
@superuser_required
def print_installment_invoice(request, franchise_pk, batch_pk, user_pk, installment_pk):
    installment = get_object_or_404(
        Installment.objects.select_related(
            'student_fee_management__user_franchise__user',
            'student_fee_management__batch_fee_management__batch__franchise'
        ),
        pk=installment_pk,
        status='paid'
    )

    student_fee = installment.student_fee_management
    user_franchise = student_fee.user_franchise
    user = user_franchise.user
    batch = student_fee.batch_fee_management.batch
    franchise = batch.franchise
    fee_management = student_fee.batch_fee_management

    # Calculate totals
    all_installments = Installment.objects.filter(student_fee_management=student_fee)
    total_paid = sum(inst.payed_amount for inst in all_installments)
    installment_balance = installment.amount - installment.payed_amount

    return render(request, 'application/print_installment_invoice.html', {
        'franchise': franchise,
        'batch': batch,
        'user': user,
        'fee_management': fee_management,
        'installment': installment,
        'total_paid': total_paid,
        'installment_balance': installment_balance,
    })
