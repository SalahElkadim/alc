from django.urls import path
from .views import GenerateExamAPIView, SubmitExamAPIView

urlpatterns = [
    path("generate/", GenerateExamAPIView.as_view(), name="generate-exam"),
    path("submit/", SubmitExamAPIView.as_view(), name="submit-exam"),
]

