from universities.views import InitializeChapaPaymentView
from django.urls import path, include
from . import views
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'users', views.UserViewSet, basename='user')

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('groups/', views.GroupList.as_view(), name='group-list'),
    
    path('chapa/initialize/', InitializeChapaPaymentView.as_view(), name='initialize_chapa_payment'),
    path('admin/stats/', views.AdminStatsView.as_view(), name='admin-stats'),
    path('universities/', views.UniversityList.as_view(), name='university-list'),
    path('universities/create/', views.create_university, name='create_university'),
    path('universities/bulk_create/', views.UniversityBulkCreate.as_view(), name='university-bulk-create'),
    path('universities/<int:pk>/', views.get_university_detail, name='university_detail'),
    path('universities/<int:pk>/update/', views.update_university, name='update_university'),
    path('universities/<int:pk>/delete/', views.delete_university, name='delete_university'),
]