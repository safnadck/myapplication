from django.urls import path
from . import views

app_name = 'application'

urlpatterns = [
    path('manage/', views.user_and_franchise_management, name='user_and_franchise_management'),
    path('franchise/<int:franchise_id>/students/', views.franchise_students, name='franchise_students'),
    path('student/<int:user_franchise_id>/edit/', views.edit_student_details, name='edit_student_details'),
    path('student/<int:user_franchise_id>/fees/', views.manage_fee_details, name='manage_fee_details'),
]