from django.urls import path
from .views import (
    MCQQuestionView, MCQQuestionDetailView,
    MatchingQuestionView, MatchingQuestionDetailView,
    TrueFalseQuestionView, TrueFalseQuestionDetailView, BookView, BookDetailView,BookQuestionsView,
    dashboard,ReadingComprehensionDetailView,ReadingComprehensionListCreateView, AddQuestionView, ReadingsByBookView
)

urlpatterns = [
    path('', dashboard, name='dashboard'),
    # Books
    path('books/', BookView.as_view(), name='book-list-create'),
    path('books/<uuid:book_id>/', BookDetailView.as_view(), name='book-detail'),
    path('books/<uuid:book_id>/questions/', BookQuestionsView.as_view(), name='book-questions'),    
    # MCQ
    path('mcq-questions/', MCQQuestionView.as_view(), name='mcq-question-list'),
    path('mcq-questions/<int:pk>/', MCQQuestionDetailView.as_view(), name='mcq-question-detail'),

    # Matching
    path('matching-questions/', MatchingQuestionView.as_view(), name='matching-question-list'),
    path('matching-questions/<int:pk>/', MatchingQuestionDetailView.as_view(), name='matching-question-detail'),
    #i

    # True/False
    path('truefalse-questions/', TrueFalseQuestionView.as_view(), name='truefalse-question-list'),
    path('truefalse-questions/<int:pk>/', TrueFalseQuestionDetailView.as_view(), name='truefalse-question-detail'),


    

    path('reading-comprehensions/', ReadingComprehensionListCreateView.as_view(), name='reading-list-create'),
    
    # عرض/تعديل/حذف قطعة معينة
    path('reading-comprehensions/<int:pk>/', ReadingComprehensionDetailView.as_view(), name='reading-detail'),
    
    # إضافة سؤال لقطعة معينة
    path('reading-comprehensions/<int:pk>/add-question/', AddQuestionView.as_view(), name='add-question'),
    
    # جلب قطع القراءة لكتاب معين
    path('books/<int:book_id>/readings/', ReadingsByBookView.as_view(), name='readings-by-book'),
    

]
