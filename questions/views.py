from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.generics import get_object_or_404
from django.shortcuts import render
from .models import (
    Book, MCQQuestion, MCQChoice,
    MatchingQuestion, MatchingPair,
    ReadingPassage, ReadingQuestion, ReadingChoice,
    TrueFalseQuestion
)
from .serializers import (
    BookSerializer,
    MCQQuestionSerializer, MCQChoiceSerializer,
    MatchingQuestionSerializer, MatchingPairSerializer,
    ReadingPassageSerializer, ReadingQuestionSerializer, ReadingChoiceSerializer,
    TrueFalseQuestionSerializer,
    # Detail serializers
    MCQQuestionDetailSerializer,
    MatchingQuestionDetailSerializer,
    ReadingQuestionDetailSerializer
)
def dashboard(request):
    return render(request,'dashboard.html' )
# ===================================================================
# Book Views
# ===================================================================
class BookView(APIView):
    """
    List all books or create a new book
    """
    permission_classes = []  # إضافة هذا السطر
    authentication_classes = []
    def get(self, request):
        books = Book.objects.all()
        serializer = BookSerializer(books, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = BookSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BookDetailView(APIView):
    def get_object(self, pk):
        try:
            return Book.objects.get(pk=pk)
        except Book.DoesNotExist:
            return None

    def get(self, request, pk):
        book = self.get_object(pk)
        if not book:
            return Response({"detail": "Book not found."}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = BookSerializer(book)
        data = serializer.data

        # استخدام related_name للوصول إلى الأسئلة مباشرة
        data['statistics'] = {
            'total_questions': (
                book.mcq_questions.count() +
                book.matching_question.count() +
                book.true_question.count() +
                book.reading_passages.count()
            ),
            'mcq_questions': book.mcq_questions.count(),
            'matching_question': book.matching_question.count(),
            'true_questions': book.true_question.count(),
            
            'reading_passages': book.reading_passages.count(),
        }
        return Response(data)

    def put(self, request, pk):
        book = self.get_object(pk)
        if not book:
            return Response({"detail": "Book not found."}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = BookSerializer(book, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        book = self.get_object(pk)
        if not book:
            return Response({"detail": "Book not found."}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = BookSerializer(book, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        book = self.get_object(pk)
        if not book:
            return Response({"detail": "Book not found."}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if book has questions before deleting
        total_questions = book.all_questions.count() + book.reading_passages.count()
        if total_questions > 0:
            return Response(
                {"detail": f"Cannot delete book. It contains {total_questions} questions/passages."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        book.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class BookQuestionsView(APIView):
    """
    Get all questions for a specific book
    """
    def get(self, request, book_id):
        try:
            book = Book.objects.get(pk=book_id)
        except Book.DoesNotExist:
            return Response({"detail": "Book not found."}, status=status.HTTP_404_NOT_FOUND)
        
        # Get all question types for this book
        # استعلم مباشر من العلاقات العكسية
        mcq_questions = book.mcq_questions.all()
        matching_questions = book.matching_question.all()
        true_question = book.true_question.all()
        reading_questions = ReadingQuestion.objects.filter(passage__book=book)

        
        data = {
            'book': BookSerializer(book).data,
            'questions': {
                'mcq': MCQQuestionSerializer(mcq_questions, many=True).data,
                'matching': MatchingQuestionSerializer(matching_questions, many=True).data,
                'truefalse': TrueFalseQuestionSerializer(true_question , many=True).data,
                'reading': ReadingQuestionSerializer(reading_questions, many=True).data,
            },
            'reading_passages': ReadingPassageSerializer(book.reading_passages.all(), many=True).data,
            'statistics': {
                'total_mcq': mcq_questions.count(),
                'total_matching': matching_questions.count(),
                'total_truefalse': true_question.count(),
                'total_reading': reading_questions.count(),
                'total_passages': book.reading_passages.count(),
            }
        }
        
        return Response(data, status=status.HTTP_200_OK)

# ===================================================================
# Reading Passage Views
# ===================================================================
class ReadingPassageView(APIView):
    """
    List all reading passages or create a new passage
    """
    def get(self, request):
        # Support filtering by book
        book_id = request.query_params.get('book', None)
        if book_id:
            passages = ReadingPassage.objects.filter(book_id=book_id)
        else:
            passages = ReadingPassage.objects.all()
        
        serializer = ReadingPassageSerializer(passages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = ReadingPassageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ReadingPassageDetailView(APIView):
    """
    Retrieve, update or delete a reading passage instance
    """
    def get_object(self, pk):
        try:
            return ReadingPassage.objects.prefetch_related('reading_questions__reading_choices').get(pk=pk)
        except ReadingPassage.DoesNotExist:
            return None

    def get(self, request, pk):
        passage = self.get_object(pk)
        if not passage:
            return Response({"detail": "Reading passage not found."}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ReadingPassageSerializer(passage)
        return Response(serializer.data)

    def put(self, request, pk):
        passage = self.get_object(pk)
        if not passage:
            return Response({"detail": "Reading passage not found."}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ReadingPassageSerializer(passage, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        passage = self.get_object(pk)
        if not passage:
            return Response({"detail": "Reading passage not found."}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ReadingPassageSerializer(passage, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        passage = self.get_object(pk)
        if not passage:
            return Response({"detail": "Reading passage not found."}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if passage has questions before deleting
        questions_count = passage.reading_questions.count()
        if questions_count > 0:
            return Response(
                {"detail": f"Cannot delete passage. It contains {questions_count} questions."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        passage.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

# ===================================================================
# Choice Detail Views (للتعديل والحذف)
# ===================================================================

class MCQChoiceDetailView(APIView):
    """
    Retrieve, update or delete an MCQ choice instance
    """
    permission_classes = []  # إضافة هذا السطر
    authentication_classes = []
    def get_object(self, pk):
        try:
            return MCQChoice.objects.select_related('question').get(pk=pk)
        except MCQChoice.DoesNotExist:
            return None

    def get(self, request, pk):
        choice = self.get_object(pk)
        if not choice:
            return Response({"detail": "MCQ choice not found."}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = MCQChoiceSerializer(choice)
        return Response(serializer.data)

    def put(self, request, pk):
        choice = self.get_object(pk)
        if not choice:
            return Response({"detail": "MCQ choice not found."}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = MCQChoiceSerializer(choice, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        choice = self.get_object(pk)
        if not choice:
            return Response({"detail": "MCQ choice not found."}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = MCQChoiceSerializer(choice, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        choice = self.get_object(pk)
        if not choice:
            return Response({"detail": "MCQ choice not found."}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if this is the last choice for the question
        question = choice.question
        choices_count = question.choices.count()
        if choices_count <= 2:
            return Response(
                {"detail": "Cannot delete choice. Question must have at least 2 choices."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if this is the only correct choice
        if choice.is_correct:
            correct_choices_count = question.mcq_choices.filter(is_correct=True).count()
            if correct_choices_count <= 1:
                return Response(
                    {"detail": "Cannot delete choice. Question must have at least 1 correct choice."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        choice.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MatchingPairDetailView(APIView):
    """
    Retrieve, update or delete a matching pair instance
    """
    permission_classes = []  # إضافة هذا السطر
    authentication_classes = []
    def get_object(self, pk):
        try:
            return MatchingPair.objects.select_related('question').get(pk=pk)
        except MatchingPair.DoesNotExist:
            return None

    def get(self, request, pk):
        pair = self.get_object(pk)
        if not pair:
            return Response({"detail": "Matching pair not found."}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = MatchingPairSerializer(pair)
        return Response(serializer.data)

    def put(self, request, pk):
        pair = self.get_object(pk)
        if not pair:
            return Response({"detail": "Matching pair not found."}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = MatchingPairSerializer(pair, data=request.data)
        if serializer.is_valid():
            # Check for duplicate values in the same question
            question = pair.question
            left_item = serializer.validated_data.get('left_item', '').strip().lower()
            right_item = serializer.validated_data.get('right_item', '').strip().lower()
            match_key = serializer.validated_data.get('match_key', '').strip().lower()
            
            # Check duplicates (excluding current pair)
            existing_pairs = question.matching_pairs.exclude(pk=pk)
            if existing_pairs.filter(left_item__iexact=left_item).exists():
                return Response(
                    {"detail": "Left item already exists in this question."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if existing_pairs.filter(right_item__iexact=right_item).exists():
                return Response(
                    {"detail": "Right item already exists in this question."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if existing_pairs.filter(match_key__iexact=match_key).exists():
                return Response(
                    {"detail": "Match key already exists in this question."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        pair = self.get_object(pk)
        if not pair:
            return Response({"detail": "Matching pair not found."}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = MatchingPairSerializer(pair, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        pair = self.get_object(pk)
        if not pair:
            return Response({"detail": "Matching pair not found."}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if this is one of the last 2 pairs for the question
        question = pair.question
        pairs_count = question.matching_pairs.count()
        if pairs_count <= 2:
            return Response(
                {"detail": "Cannot delete pair. Question must have at least 2 pairs."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        pair.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReadingChoiceDetailView(APIView):
    """
    Retrieve, update or delete a reading choice instance
    """
    def get_object(self, pk):
        try:
            return ReadingChoice.objects.select_related('question').get(pk=pk)
        except ReadingChoice.DoesNotExist:
            return None

    def get(self, request, pk):
        choice = self.get_object(pk)
        if not choice:
            return Response({"detail": "Reading choice not found."}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ReadingChoiceSerializer(choice)
        return Response(serializer.data)

    def put(self, request, pk):
        choice = self.get_object(pk)
        if not choice:
            return Response({"detail": "Reading choice not found."}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ReadingChoiceSerializer(choice, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        choice = self.get_object(pk)
        if not choice:
            return Response({"detail": "Reading choice not found."}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ReadingChoiceSerializer(choice, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        choice = self.get_object(pk)
        if not choice:
            return Response({"detail": "Reading choice not found."}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if this is one of the last 2 choices for the question
        question = choice.question
        choices_count = question.reading_choices.count()
        if choices_count <= 2:
            return Response(
                {"detail": "Cannot delete choice. Question must have at least 2 choices."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        choice.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

# ===================================================================
# Utility Views (إضافات مفيدة)
# ===================================================================


    # views.py


class MCQQuestionView(APIView):
    permission_classes = []  # إضافة هذا السطر
    authentication_classes = []
    def get(self, request):
        questions = MCQQuestion.objects.prefetch_related('choices').all()
        serializer = MCQQuestionSerializer(questions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = MCQQuestionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MCQQuestionDetailView(APIView):
    permission_classes = []  # إضافة هذا السطر
    authentication_classes = []
    def get_object(self, pk):
        return get_object_or_404(MCQQuestion, pk=pk)

    def get(self, request, pk):
        question = self.get_object(pk)
        serializer = MCQQuestionSerializer(question)
        return Response(serializer.data)

    def put(self, request, pk):
        question = self.get_object(pk)
        serializer = MCQQuestionSerializer(question, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        question = self.get_object(pk)
        question.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

# views.py

from .models import ReadingQuestion
from .serializers import ReadingQuestionSerializer

class ReadingQuestionView(APIView):
    def get(self, request):
        questions = ReadingQuestion.objects.prefetch_related('choices').all()
        serializer = ReadingQuestionSerializer(questions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = ReadingQuestionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ReadingQuestionDetailView(APIView):
    def get_object(self, pk):
        return get_object_or_404(ReadingQuestion, pk=pk)

    def get(self, request, pk):
        question = self.get_object(pk)
        serializer = ReadingQuestionSerializer(question)
        return Response(serializer.data)

    def put(self, request, pk):
        question = self.get_object(pk)
        serializer = ReadingQuestionSerializer(question, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        question = self.get_object(pk)
        question.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

from .models import MatchingQuestion
from .serializers import MatchingQuestionSerializer

class MatchingQuestionView(APIView):
    permission_classes = []  # إضافة هذا السطر
    authentication_classes = []
    def get(self, request):
        questions = MatchingQuestion.objects.prefetch_related('pairs').all()
        serializer = MatchingQuestionSerializer(questions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = MatchingQuestionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MatchingQuestionDetailView(APIView):
    permission_classes = []  # إضافة هذا السطر
    authentication_classes = []
    def get_object(self, pk):
        return get_object_or_404(MatchingQuestion, pk=pk)

    def get(self, request, pk):
        question = self.get_object(pk)
        serializer = MatchingQuestionSerializer(question)
        return Response(serializer.data)

    def put(self, request, pk):
        question = self.get_object(pk)
        serializer = MatchingQuestionSerializer(question, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        question = self.get_object(pk)
        question.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

from .models import TrueFalseQuestion
from .serializers import TrueFalseQuestionSerializer

class TrueFalseQuestionView(APIView):
    def get(self, request):
        questions = TrueFalseQuestion.objects.all()
        serializer = TrueFalseQuestionSerializer(questions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = TrueFalseQuestionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TrueFalseQuestionDetailView(APIView):
    def get_object(self, pk):
        return get_object_or_404(TrueFalseQuestion, pk=pk)

    def get(self, request, pk):
        question = self.get_object(pk)
        serializer = TrueFalseQuestionSerializer(question)
        return Response(serializer.data)

    def put(self, request, pk):
        question = self.get_object(pk)
        serializer = TrueFalseQuestionSerializer(question, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        question = self.get_object(pk)
        question.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
