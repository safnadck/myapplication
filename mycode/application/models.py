from django.db import models
from django.contrib.auth.models import User
from common.djangoapps.student.models import UserProfile

class Franchise(models.Model):
    name = models.CharField(max_length=150)
    location = models.CharField(max_length=255)
    joining_date = models.DateField()

    def __str__(self):
        return f"{self.name} - {self.location}"

class UserFranchise(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='franchise_info')
    franchise = models.ForeignKey(Franchise, on_delete=models.SET_NULL, null=True, blank=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.franchise.name if self.franchise else 'No Franchise'}"