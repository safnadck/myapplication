from django.urls import path
from . import views

app_name = 'application'

urlpatterns = [
    path('home/', views.homepage, name='homepage'),
    path('franchises/', views.franchise_list, name='franchise_list'),
    path('franchise/register/', views.franchise_register, name='franchise_register'),
    path('franchise/<int:pk>/edit/', views.franchise_edit, name='franchise_edit'),
    path('franchise/<int:pk>/report/', views.franchise_report, name='franchise_report'),
    path('franchise/<int:pk>/batch/add/', views.batch_create, name='batch_create'),
    path('franchise/<int:franchise_pk>/batch/<int:batch_pk>/students/', views.batch_students, name='batch_students'),
    path('franchise/<int:franchise_pk>/batch/<int:batch_pk>/student/<int:user_pk>/', views.student_detail, name='student_detail'),
    path('franchise/<int:franchise_pk>/batch/<int:batch_pk>/student/<int:user_pk>/edit/', views.edit_student_details, name='edit_student_details'),
    path('franchise/<int:franchise_pk>/batch/<int:batch_pk>/register/', views.batch_user_register, name='batch_user_register'),
    path('franchise/<int:franchise_pk>/batch/<int:batch_pk>/fee-management/', views.batch_fee_management, name='batch_fee_management'),
    path('franchise/<int:franchise_pk>/batch/<int:batch_pk>/student-fee-management/<int:user_pk>/', views.student_fee_management, name='student_fee_management'),
    path('franchise/<int:franchise_pk>/batch/<int:batch_pk>/student-fee-management/<int:user_pk>/edit-installment/', views.edit_installment_setup, name='edit_installment_setup'),
]