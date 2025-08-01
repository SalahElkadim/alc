from django.urls import path
from .views import (
    MCQQuestionView, MCQQuestionDetailView,
    ReadingQuestionView, ReadingQuestionDetailView,
    MatchingQuestionView, MatchingQuestionDetailView,
    TrueFalseQuestionView, TrueFalseQuestionDetailView, BookView, BookDetailView, ReadingPassageView, ReadingPassageDetailView, MCQChoiceDetailView,BookQuestionsView,
    MatchingPairDetailView, ReadingChoiceDetailView
)

urlpatterns = [
    # MCQ
    path('mcq-questions/', MCQQuestionView.as_view(), name='mcq-question-list'),
    path('mcq-questions/<int:pk>/', MCQQuestionDetailView.as_view(), name='mcq-question-detail'),

    # Reading
    path('reading-questions/', ReadingQuestionView.as_view(), name='reading-question-list'),
    path('reading-questions/<int:pk>/', ReadingQuestionDetailView.as_view(), name='reading-question-detail'),

    # Matching
    path('matching-questions/', MatchingQuestionView.as_view(), name='matching-question-list'),
    path('matching-questions/<int:pk>/', MatchingQuestionDetailView.as_view(), name='matching-question-detail'),



    # True/False
    path('truefalse-questions/', TrueFalseQuestionView.as_view(), name='truefalse-question-list'),
    path('truefalse-questions/<int:pk>/', TrueFalseQuestionDetailView.as_view(), name='truefalse-question-detail'),


    # Books
    path('books/', BookView.as_view(), name='book-list-create'),
    path('books/<int:pk>/', BookDetailView.as_view(), name='book-detail'),
    path('books/<int:book_id>/questions/', BookQuestionsView.as_view(), name='book-questions'),

    # Reading Passages  
    path('passages/', ReadingPassageView.as_view(), name='passage-list-create'),
    path('passages/<int:pk>/', ReadingPassageDetailView.as_view(), name='passage-detail'),
    
    # Choices (for editing individual choices)
    path('mcq-choices/<int:pk>/', MCQChoiceDetailView.as_view(), name='mcq-choice-detail'),
    path('matching-pairs/<int:pk>/', MatchingPairDetailView.as_view(), name='matching-pair-detail'),
    path('reading-choices/<int:pk>/', ReadingChoiceDetailView.as_view(), name='reading-choice-detail'),
    # ... etc

]
