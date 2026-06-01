from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from main.views import CustomPasswordResetView
from main.views import CustomPasswordResetConfirmView
from main.views import save_recommendation, delete_recommendation, clear_recommendations, saved_recommendations

urlpatterns = [
    path('', include('main.urls')),
    path('admin/', admin.site.urls),


    # Відновлення пароля
    path('password_reset/', CustomPasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'),
    
    # Логіка для рекомендацій
    path('recommendations/save/',         save_recommendation,  name='save_recommendation'),
    path('recommendations/',               saved_recommendations, name='saved_recommendations'),
    path('recommendations/delete/<int:rec_id>/', delete_recommendation, name='delete_recommendation'),
    path('recommendations/clear/',         clear_recommendations, name='clear_recommendations'),
]