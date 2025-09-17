
from django.contrib import admin
from django.urls import path, include,handler404
from django.shortcuts import render

urlpatterns = [
    path('admin/', admin.site.urls),
    path('users/',include('users.urls')),
    path('questions/',include('questions.urls')),
    path('exam/',include('exam.urls')),
    path('payments/',include('payments.urls')),

]

def custom_page_not_found(request, exception):
    return render(request, "404.html", status=404)

handler404 = custom_page_not_found
