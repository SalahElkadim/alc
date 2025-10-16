from django.contrib import admin
from .models import ExamResult, Exam,ExamQuestion

admin.site.register(ExamResult)
admin.site.register(Exam)
admin.site.register(ExamQuestion)