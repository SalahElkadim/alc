from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Router للـ ViewSet (اختياري)
router = DefaultRouter()
router.register(r'exams', views.ExamViewSet, basename='exam')

app_name = 'exams'

urlpatterns = [
    # APIs للطلاب
    path('generate/', views.GenerateExamView.as_view(), name='generate-exam'),
    path('<int:exam_id>/', views.GetExamView.as_view(), name='get-exam'),
    path('<int:exam_id>/submit/', views.SubmitExamView.as_view(), name='submit-exam'),
    path('<int:exam_id>/result/', views.ExamResultView.as_view(), name='exam-result'),
    path('my-exams/', views.StudentExamsView.as_view(), name='student-exams'),
    
    # APIs للإحصائيات
    path('statistics/', views.ExamStatisticsView.as_view(), name='exam-statistics'),
    
    # APIs للإدارة والمدرسين
    path('admin/list/', views.ExamAdminListView.as_view(), name='admin-exam-list'),
    path('admin/health-check/', views.ExamHealthCheckView.as_view(), name='exam-health-check'),
    
    # ViewSet URLs (بديل)
    path('api/', include(router.urls)),
]

# URLs إضافية للتطوير والاختبار
from django.conf import settings
if settings.DEBUG:
    urlpatterns += [
        # API Documentation
        path('docs/', views.ExamAPIDocumentationView.as_view(), name='api-docs'),
    ]