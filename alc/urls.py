
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render

urlpatterns = [
    path('admin/', admin.site.urls),
    path('users/',include('users.urls')),
    path('questions/',include('questions.urls')),
    path('exam/',include('exam.urls')),
    path('payments/',include('payments.urls')),

]

handler404 = "users.views.custom_404"
