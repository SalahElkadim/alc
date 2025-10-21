from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.generics import get_object_or_404
from django.shortcuts import render
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import status, permissions
from users.models import UserBook
from .models import (
    Book, MCQQuestion, MCQChoice,
    MatchingQuestion, MatchingPair,
    TrueFalseQuestion, ReadingComprehension
)
from .serializers import (
    BookSerializer,
    MCQQuestionSerializer, MCQChoiceSerializer,
    MatchingQuestionSerializer, MatchingPairSerializer,
    TrueFalseQuestionSerializer, ReadingComprehensionSerializer


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
    authentication_classes = [JWTAuthentication]

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get(self, request):
        books = Book.objects.all()
        serializer = BookSerializer(books, many=True)
        books_data = serializer.data

        # 🔥 لو المستخدم مسجل دخوله، نضيف حالة كل كتاب (مفتوح/مقفول)
        if request.user.is_authenticated:
            open_books = UserBook.objects.filter(
                user=request.user, status='unlocked'
            ).values_list('book_id', flat=True)

            for book in books_data:
                book['is_unlocked'] = str(book['id']) in [str(bid) for bid in open_books]

        else:
            for book in books_data:
                book['is_unlocked'] = False  # زائر فقط

        return Response(books_data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = BookSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BookDetailView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]  # الكل يقدر يشوف التفاصيل
        return [permissions.IsAdminUser()] 
    authentication_classes = [JWTAuthentication]
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
                book.reading_comprehensions.count()
            ),
            'mcq_questions': book.mcq_questions.count(),
            'matching_question': book.matching_question.count(),
            'true_questions': book.true_question.count(),           
            'reading_comprehensions': book.reading_comprehensions.count(),
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
        book.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class BookQuestionsView(APIView):
    """
    Get all questions for a specific book
    """
    permission_classes = [permissions.IsAdminUser]
    authentication_classes = [JWTAuthentication]
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

        
        data = {
            'book': BookSerializer(book).data,
            'questions': {
                'mcq': MCQQuestionSerializer(mcq_questions, many=True).data,
                'matching': MatchingQuestionSerializer(matching_questions, many=True).data,
                'truefalse': TrueFalseQuestionSerializer(true_question , many=True).data,
            },
            'reading_passages': ReadingComprehensionSerializer(book.reading_comprehensions.all(), many=True).data,
            'statistics': {
                'total_mcq': mcq_questions.count(),
                'total_matching': matching_questions.count(),
                'total_truefalse': true_question.count(),
            }
        }
        
        return Response(data, status=status.HTTP_200_OK)


# ===================================================================
# Choice Detail Views (للتعديل والحذف)
# ===================================================================

class MCQChoiceDetailView(APIView):
    """
    Retrieve, update or delete an MCQ choice instance
    """
    permission_classes = [permissions.IsAdminUser]
    authentication_classes = [JWTAuthentication]
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
    permission_classes = [permissions.IsAdminUser]
    authentication_classes = [JWTAuthentication]
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



# ===================================================================
# Utility Views (إضافات مفيدة)
# ===================================================================


    # views.py


class MCQQuestionView(APIView):
    permission_classes = [permissions.IsAdminUser]
    authentication_classes = [JWTAuthentication]
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
    permission_classes = [permissions.IsAdminUser]
    authentication_classes = [JWTAuthentication]
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

from .models import MatchingQuestion
from .serializers import MatchingQuestionSerializer

class MatchingQuestionView(APIView):
    permission_classes = [permissions.IsAdminUser]
    authentication_classes = [JWTAuthentication]
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
    permission_classes = [permissions.IsAdminUser]
    authentication_classes = [JWTAuthentication]
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
    permission_classes = [permissions.IsAdminUser]
    authentication_classes = [JWTAuthentication]
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
    permission_classes = [permissions.IsAdminUser]
    authentication_classes = [JWTAuthentication]
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


class ReadingComprehensionListCreateView(APIView):
    """
    GET: عرض جميع قطع القراءة
    POST: إضافة قطعة قراءة جديدة
    """
    permission_classes = [permissions.IsAdminUser]
    authentication_classes = [JWTAuthentication]
    def get(self, request):
        """عرض جميع قطع القراءة"""
        try:
            comprehensions = ReadingComprehension.objects.select_related('book').all()
            serializer = ReadingComprehensionSerializer(comprehensions, many=True)
            
            return Response({
                'success': True,
                'count': comprehensions.count(),
                'data': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'خطأ في جلب البيانات: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request):
        """إضافة قطعة قراءة جديدة"""
        try:
            serializer = ReadingComprehensionSerializer(data=request.data)
            
            if serializer.is_valid():
                # التحقق من وجود الكتاب
                book_id = request.data.get('book')
                if not Book.objects.filter(id=book_id).exists():
                    return Response({
                        'success': False,
                        'message': 'الكتاب المحدد غير موجود'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                comprehension = serializer.save()
                
                return Response({
                    'success': True,
                    'message': 'تم إضافة قطعة القراءة بنجاح',
                    'data': serializer.data
                }, status=status.HTTP_201_CREATED)
            
            return Response({
                'success': False,
                'message': 'خطأ في البيانات المرسلة',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'خطأ في إضافة القطعة: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReadingComprehensionDetailView(APIView):
    """
    GET: عرض قطعة قراءة محددة
    PUT: تعديل كامل لقطعة القراءة
    PATCH: تعديل جزئي لقطعة القراءة
    DELETE: حذف قطعة القراءة
    """
    permission_classes = [permissions.IsAdminUser]
    authentication_classes = [JWTAuthentication]
    def get_object(self, pk):
        """الحصول على قطعة القراءة أو إرجاع 404"""
        return get_object_or_404(ReadingComprehension, pk=pk)
    
    def get(self, request, pk):
        """عرض قطعة قراءة محددة"""
        try:
            comprehension = self.get_object(pk)
            serializer = ReadingComprehensionSerializer(comprehension)
            
            return Response({
                'success': True,
                'data': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'خطأ في جلب البيانات: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def put(self, request, pk):
        """تعديل قطعة قراءة (تعديل كامل)"""
        try:
            comprehension = self.get_object(pk)
            serializer = ReadingComprehensionSerializer(comprehension, data=request.data)
            
            if serializer.is_valid():
                # التحقق من وجود الكتاب إذا تم تعديله
                book_id = request.data.get('book')
                if book_id and not Book.objects.filter(id=book_id).exists():
                    return Response({
                        'success': False,
                        'message': 'الكتاب المحدد غير موجود'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                serializer.save()
                
                return Response({
                    'success': True,
                    'message': 'تم تعديل قطعة القراءة بنجاح',
                    'data': serializer.data
                }, status=status.HTTP_200_OK)
            
            return Response({
                'success': False,
                'message': 'خطأ في البيانات المرسلة',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'خطأ في تعديل القطعة: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def patch(self, request, pk):
        """تعديل جزئي لقطعة القراءة"""
        try:
            comprehension = self.get_object(pk)
            serializer = ReadingComprehensionSerializer(comprehension, data=request.data, partial=True)
            
            if serializer.is_valid():
                # التحقق من وجود الكتاب إذا تم تعديله
                book_id = request.data.get('book')
                if book_id and not Book.objects.filter(id=book_id).exists():
                    return Response({
                        'success': False,
                        'message': 'الكتاب المحدد غير موجود'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                serializer.save()
                
                return Response({
                    'success': True,
                    'message': 'تم تعديل قطعة القراءة بنجاح',
                    'data': serializer.data
                }, status=status.HTTP_200_OK)
            
            return Response({
                'success': False,
                'message': 'خطأ في البيانات المرسلة',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'خطأ في تعديل القطعة: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request, pk):
        """حذف قطعة قراءة"""
        try:
            comprehension = self.get_object(pk)
            title = comprehension.title  # حفظ العنوان قبل الحذف
            comprehension.delete()
            
            return Response({
                'success': True,
                'message': f'تم حذف قطعة القراءة "{title}" بنجاح'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'خطأ في حذف القطعة: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AddQuestionView(APIView):
    """إضافة سؤال جديد لقطعة قراءة محددة"""
    permission_classes = [permissions.IsAdminUser]
    authentication_classes = [JWTAuthentication]
    def post(self, request, pk):
        """إضافة سؤال جديد لقطعة القراءة"""
        try:
            comprehension = get_object_or_404(ReadingComprehension, pk=pk)
            
            question = request.data.get('question')
            choices = request.data.get('choices')
            correct_answer = request.data.get('correct_answer')
            
            # التحقق من البيانات المطلوبة
            if not all([question, choices, correct_answer]):
                return Response({
                    'success': False,
                    'message': 'يجب إرسال السؤال والاختيارات والإجابة الصحيحة'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # التحقق من أن الاختيارات قائمة
            if not isinstance(choices, list) or len(choices) < 2:
                return Response({
                    'success': False,
                    'message': 'الاختيارات يجب أن تكون قائمة تحتوي على خيارين على الأقل'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # التحقق من أن الإجابة الصحيحة من ضمن الاختيارات
            if correct_answer not in choices:
                return Response({
                    'success': False,
                    'message': 'الإجابة الصحيحة يجب أن تكون من ضمن الاختيارات'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # إضافة السؤال
            comprehension.add_question(question, choices, correct_answer)
            
            return Response({
                'success': True,
                'message': 'تم إضافة السؤال بنجاح',
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'خطأ في إضافة السؤال: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReadingsByBookView(APIView):
    """جلب قطع القراءة الخاصة بكتاب معين"""
    permission_classes = [permissions.IsAdminUser]
    authentication_classes = [JWTAuthentication]
    def get(self, request, book_id):
        """جلب جميع قطع القراءة لكتاب محدد"""
        try:
            # التحقق من وجود الكتاب
            book = get_object_or_404(Book, pk=book_id)
            
            comprehensions = ReadingComprehension.objects.filter(book=book)
            serializer = ReadingComprehensionSerializer(comprehensions, many=True)
            
            return Response({
                'success': True,
                'book_title': book.title,
                'count': comprehensions.count(),
                'data': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'خطأ في جلب البيانات: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)