from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from .forms import FranchiseForm, BatchForm, FranchiseUserRegistrationForm, BatchFeeManagementForm, StudentFeeManagementForm, InstallmentForm, PaymentForm, StudentEditForm
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
        existing_installments = Installment.objects.filter(student_fee_management=student_fee)
        for installment in existing_installments:
            status_key = f'status_{installment.id}'
            if status_key in request.POST:
                new_status = request.POST[status_key]
                if new_status in ['pending', 'paid', 'overdue']:
                    installment.status = new_status
                    if new_status == 'paid' and not installment.payment_date:
                        installment.payment_date = timezone.now().date()
                    elif new_status != 'paid':
                        installment.payment_date = None
                    installment.save()

        total_paid = sum(inst.amount for inst in Installment.objects.filter(student_fee_management=student_fee, status='paid'))
        student_fee.remaining_amount = fee_management.remaining_amount - total_paid
        student_fee.save()

        return redirect('application:student_fee_management', franchise_pk=franchise.pk, batch_pk=batch.pk, user_pk=user.pk)

    existing_installments = Installment.objects.filter(student_fee_management=student_fee).order_by('due_date')
    installments = [{'installment': installment, 'repayment_period_days': installment.repayment_period_days} for installment in existing_installments]

    total_paid = sum(installment.amount for installment in existing_installments if installment.status == 'paid')
    total_pending = sum(installment.amount for installment in existing_installments if installment.status != 'paid')

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


@login_required
@superuser_required
def edit_installment_setup(request, franchise_pk, batch_pk, user_pk):
    franchise = get_object_or_404(Franchise, pk=franchise_pk)
    batch = get_object_or_404(Batch, pk=batch_pk, franchise=franchise)
    user = get_object_or_404(User, pk=user_pk)

    fee_management = get_object_or_404(BatchFeeManagement, batch=batch)
    user_franchise = get_object_or_404(UserFranchise, user=user, franchise=franchise, batch=batch)
    student_fee = get_object_or_404(StudentFeeManagement, user_franchise=user_franchise)

    InstallmentFormSet = modelformset_factory(Installment, form=InstallmentForm, extra=0, can_delete=True)

    if request.method == "POST":
        formset = InstallmentFormSet(request.POST, queryset=Installment.objects.filter(student_fee_management=student_fee))
        if formset.is_valid():
            instances = formset.save(commit=False)
            
            for instance in instances:
                instance.student_fee_management = student_fee
                instance.save()
            
            for obj in formset.deleted_objects:
                obj.delete()
            
            total_pending = sum(inst.amount for inst in Installment.objects.filter(student_fee_management=student_fee, status='pending'))
            student_fee.remaining_amount = total_pending
            student_fee.save()
            
            return redirect('application:student_fee_management', franchise_pk=franchise.pk, batch_pk=batch.pk, user_pk=user.pk)
    else:
        formset = InstallmentFormSet(queryset=Installment.objects.filter(student_fee_management=student_fee))

    return render(request, 'application/edit_installment_setup.html', {
        'franchise': franchise,
        'batch': batch,
        'user': user,
        'formset': formset,
        'student_fee': student_fee,
    })