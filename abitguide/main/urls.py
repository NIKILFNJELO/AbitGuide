from django.urls import path
from . import views

urlpatterns = [
    
    path('', views.home, name='home'),
    path('contacts/', views.contacts, name='contacts'),
    path('universities/', views.universities, name='universities'),
    path('profile/', views.profile, name='profile'),
    path('sources/', views.sources, name='sources'),
    path('registration/', views.registration, name='registration'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),


    # Спеціальності
    path('universities/<slug:slug>/programs/<str:letter>/', views.university_programs_letter, name='university_programs_letter'),
    path('university/<slug:slug>/programs/', views.university_programs, name='university_programs'),


    # Редагування
    path('universities/<slug:slug>/edit-name/', views.university_edit_name, name='university_edit_name'),
    path('universities/<slug:slug>/about/', views.university_about, name='university_about'),
    path('universities/<slug:slug>/about/edit/', views.university_about_edit, name='university_about_edit'),
    path('universities/<slug:slug>/contacts/', views.university_contacts, name='university_contacts'),
    path('universities/<slug:slug>/contacts/edit/', views.university_contacts_edit, name='university_contacts_edit'),
    path('universities/<slug:slug>/website/', views.university_website, name='university_website'),
    path('universities/<slug:slug>/website/edit/', views.university_website_edit, name='university_website_edit'),
    path('universities/<slug:slug>/dates/', views.university_dates, name='university_dates'),
    path('universities/<slug:slug>/dates/edit/', views.university_dates_edit, name='university_dates_edit'),
    path('universities/<slug:slug>/program/create/', views.university_program_create, name='university_program_create'),    
    path('universities/<slug:slug>/specialties/<int:specialty_id>/edit/', views.specialty_edit, name='specialty_edit'),
    path('universities/<slug:slug>/specialties/create/', views.specialty_create, name='specialty_create'),


    # Видалення
    path('universities/<slug:slug>/specialties/<int:specialty_id>/delete/', views.specialty_delete, name='specialty_delete'),
    path('universities/<slug:slug>/programs/<str:letter>/delete/', views.university_program_delete, name='university_program_delete'),
    path('universities/<slug:slug>/delete/', views.university_delete, name='university_delete'),


    # Універсальна сторінка університету
    path('universities/<slug:slug>/', views.university_detail, name='university_detail'),

    # Адмін
    path('admin/credentials/', views.admin_credentials, name='admin_credentials'),
    path('admin/credentials/create/', views.admin_credential_create, name='admin_credential_create'),
    path('admin/users/', views.admin_users, name='admin_users'),
    path('admin/university/create/', views.admin_university_create, name='admin_university_create'),
]