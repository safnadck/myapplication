from django.urls import path
from . import views

app_name = 'application'

urlpatterns = [
    path('franchises/', views.franchise_list, name='franchise_list'),
    path('franchise/<int:franchise_id>/students/', views.franchise_students, name='franchise_students'),
    path('student/<int:user_franchise_id>/fees/', views.student_fee_details, name='student_fee_details'),
]
