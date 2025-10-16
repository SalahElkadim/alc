from django.urls import path
from .views import GenerateExamAPIView, SubmitExamAPIView, ExamResultListAPIView

urlpatterns = [
    path("generate/", GenerateExamAPIView.as_view(), name="generate-exam"),
    path("submit/", SubmitExamAPIView.as_view(), name="submit-exam"),
    path("results/", ExamResultListAPIView.as_view(), name="exam-results"),

]

