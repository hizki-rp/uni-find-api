from django.urls import path, include
from . import views

urlpatterns = [
    path('universities/', views.get_universities, name='get_universities'),
    path('universities/create/', views.create_university, name='create_university'),
    path('universities/', views.UniversityList.as_view()),
    path('universities/<int:pk>/', views.get_university_detail, name='university_detail'),

    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.jwt')),  # Enables JWT login/logout

    path('universities/<int:pk>/update/', views.update_university, name='update_university'),
]