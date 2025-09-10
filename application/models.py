from django.db import models
from django.contrib.auth.models import User
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview

class Franchise(models.Model):
    name = models.CharField(max_length=255)
    coordinator = models.CharField(max_length=255)
    contact_no = models.CharField(max_length=20)
    email = models.EmailField()
    location = models.CharField(max_length=255, blank=True, null=True)
    registration_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return self.name


class UserFranchise(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    franchise = models.ForeignKey(Franchise, on_delete=models.SET_NULL, null=True, blank=True)
    batch = models.ForeignKey("Batch", on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        franchise_name = self.franchise.name if self.franchise else "No Franchise"
        batch_name = self.batch.batch_no if self.batch else "No Batch"
        return f"{self.user.username} - {franchise_name} - {batch_name}"


class Batch(models.Model):
    batch_no = models.CharField(max_length=50, unique=True)
    fees = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    course = models.ForeignKey(CourseOverview, on_delete=models.CASCADE, related_name='batches')
    franchise = models.ForeignKey(Franchise, on_delete=models.CASCADE, related_name='batches')

    def __str__(self):
        return f"Batch {self.batch_no} - {self.course.display_name if self.course else 'No Course'}"


class BatchFeeManagement(models.Model):
    batch = models.OneToOneField(Batch, on_delete=models.CASCADE, related_name='fee_management')
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    remaining_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    installment_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    repayment_period_days = models.PositiveIntegerField(default=30)

    def save(self, *args, **kwargs):
        self.remaining_amount = self.batch.fees - self.discount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Fee Management for {self.batch}"


class StudentFeeManagement(models.Model):
    user_franchise = models.OneToOneField(UserFranchise, on_delete=models.CASCADE, related_name='fee_management')
    batch_fee_management = models.ForeignKey(BatchFeeManagement, on_delete=models.CASCADE)
    remaining_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        if not self.remaining_amount:
            self.remaining_amount = self.batch_fee_management.remaining_amount
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Fee Management for {self.user_franchise.user.username}"


class Installment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ]
    student_fee_management = models.ForeignKey(StudentFeeManagement, on_delete=models.CASCADE, related_name='installments')
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    payment_date = models.DateField(blank=True, null=True)
    repayment_period_days = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Installment {self.id} for {self.student_fee_management} - {self.status}"


class InstallmentTemplate(models.Model):
    batch_fee_management = models.ForeignKey(BatchFeeManagement, on_delete=models.CASCADE, related_name='installment_templates')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    repayment_period_days = models.PositiveIntegerField()

    def __str__(self):
        return f"Installment Template: ${self.amount} every {self.repayment_period_days} days"


class Payment(models.Model):
    installment = models.OneToOneField(Installment, on_delete=models.CASCADE, related_name='payment')
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Payment for Installment {self.installment.id}"