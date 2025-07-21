from django.db import models
from django.contrib.auth.models import User


class Franchise(models.Model):
    name = models.CharField(max_length=150)
    location = models.CharField(max_length=255)
    joining_date = models.DateField()

    def __str__(self):
        return f"{self.name} - {self.location}"

class UserFranchise(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    franchise = models.ForeignKey(Franchise, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.franchise.name if self.franchise else 'No Franchise'}"
    
class FranchiseStudentDetails(models.Model):
    user_franchise = models.OneToOneField(UserFranchise, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    duration = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"Details for {self.user_franchise.user.username}"

class StudentFeeDetail(models.Model):
    user_franchise = models.OneToOneField(UserFranchise, on_delete=models.CASCADE, related_name='fee_detail', null=True, blank=True)
    total_fees = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_installments = models.IntegerField(default=0, null=True, blank=True)
    installments_paid = models.IntegerField(default=0, null=True, blank=True)
    fees_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)

    @property
    def pending_fees(self):
        # Calculate pending fees based on total fees and installments paid
        if self.total_installments and self.total_installments > 0:
            installment_amount = self.total_fees / self.total_installments
            paid_amount = installment_amount * self.installments_paid
            pending = self.total_fees - paid_amount
            return max(pending, 0)
        else:
            return self.total_fees

    def __str__(self):
        return f"Fee details for {self.user_franchise.user.username}"

    

 
