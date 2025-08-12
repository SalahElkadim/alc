from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
import random
import json
from django.db import models

from .models import Exam, ExamQuestion
from .serializers import (
    ExamSerializer, ExamDetailSerializer, ExamResultSerializer,
    GenerateExamRequestSerializer, SubmitExamRequestSerializer,
    GenerateExamResponseSerializer, SubmitExamResponseSerializer,
    StudentExamsListSerializer
)
from questions.models import MCQQuestion, MatchingQuestion, TrueFalseQuestion, ReadingComprehension, Book


class GenerateExamView(APIView):
    permission_classes = []  # إضافة هذا السطر
    authentication_classes = []    
    def post(self, request):
        # استخدام Serializer للتحقق من البيانات
        serializer = GenerateExamRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data
        student = request.user
        book_id = validated_data['book_id']
        duration = validated_data['duration']
        
        try:
            book = Book.objects.get(id=book_id)
        except Book.DoesNotExist:
            return Response({"error": "Book not found"}, status=status.HTTP_404_NOT_FOUND)

        # التحقق من عدم وجود امتحان نشط للطالب في نفس الكتاب
        active_exam = Exam.objects.filter(
            student=student, 
            book=book, 
            is_finished=False
        ).first()
        
        if active_exam:
            return Response({
                "error": "You already have an active exam for this book",
                "active_exam_id": active_exam.id
            }, status=status.HTTP_400_BAD_REQUEST)

        # إنشاء الامتحان مع transaction للأمان
        try:
            with transaction.atomic():
                exam = Exam.objects.create(
                    student=student,
                    book=book,
                    duration_minutes=duration
                )

                # جلب الأسئلة من كل نوع
                mcqs = list(MCQQuestion.objects.filter(book=book))
                tfs = list(TrueFalseQuestion.objects.filter(book=book))
                matchings = list(MatchingQuestion.objects.filter(book=book))
                readings = list(ReadingComprehension.objects.filter(book=book))

                # التحقق من وجود أسئلة كافية
                total_available = len(mcqs) + len(tfs) + len(matchings) + sum(len(r.questions_data) for r in readings)
                if total_available < 10:  # الحد الأدنى للأسئلة
                    return Response({
                        "error": f"Not enough questions available. Found {total_available}, minimum required is 10"
                    }, status=status.HTTP_400_BAD_REQUEST)

                # خلط الأسئلة عشوائياً
                random.shuffle(mcqs)
                random.shuffle(tfs)
                random.shuffle(matchings)
                random.shuffle(readings)

                # توزيع أفضل للأسئلة
                question_counts = {
                    'mcq': min(5, len(mcqs)),
                    'truefalse': min(5, len(tfs)),
                    'matching': min(3, len(matchings)),
                    'reading': 0
                }

                # حساب عدد أسئلة القراءة المتاحة
                reading_questions_available = []
                for reading in readings:
                    if reading.questions_data:
                        for qa in reading.questions_data:
                            if qa.get('question') and qa.get('correct_answer'):
                                reading_questions_available.append((reading, qa))
                
                random.shuffle(reading_questions_available)
                question_counts['reading'] = min(5, len(reading_questions_available))

                # حفظ أسئلة MCQ
                for q in mcqs[:question_counts['mcq']]:
                    correct_choice = q.choices.filter(is_correct=True).first()
                    if not correct_choice:
                        continue
                    
                    choices_data = []
                    for choice in q.choices.all():
                        choices_data.append({
                            'id': choice.id,
                            'text': choice.text
                        })
                    
                    ExamQuestion.objects.create(
                        exam=exam,
                        question_type='mcq',
                        question_id=q.id,
                        question_text=q.text,
                        correct_answer={
                            'answer_id': correct_choice.id,
                            'answer_text': correct_choice.text,
                            'choices': choices_data
                        },
                        points=1
                    )

                # حفظ أسئلة True/False
                for q in tfs[:question_counts['truefalse']]:
                    ExamQuestion.objects.create(
                        exam=exam,
                        question_type='truefalse',
                        question_id=q.id,
                        question_text=q.question_text,
                        correct_answer={'answer': q.is_true},
                        points=1
                    )

                # حفظ أسئلة Matching
                for q in matchings[:question_counts['matching']]:
                    if not q.pairs.exists():
                        continue
                    
                    pairs_data = []
                    correct_matches = {}
                    
                    for pair in q.pairs.all():
                        pairs_data.append({
                            'id': pair.id,
                            'left': pair.left_item,
                            'right': pair.right_item
                        })
                        correct_matches[pair.left_item] = pair.right_item
                    
                    ExamQuestion.objects.create(
                        exam=exam,
                        question_type='matching',
                        question_id=q.id,
                        question_text=q.text or q.question_text,
                        correct_answer={
                            'matches': correct_matches,
                            'pairs': pairs_data
                        },
                        points=2
                    )

                # حفظ أسئلة Reading
                for reading, qa in reading_questions_available[:question_counts['reading']]:
                    ExamQuestion.objects.create(
                        exam=exam,
                        question_type='reading',
                        question_id=reading.id,
                        question_text=qa.get("question", ""),
                        correct_answer={
                            'answer': qa.get("correct_answer"),
                            'choices': qa.get("choices", []),
                            'reading_title': reading.title,
                            'reading_content': reading.content
                        },
                        points=1.5
                    )

                # التحقق من إنشاء أسئلة فعلياً
                questions_created = exam.exam_questions.count()
                if questions_created == 0:
                    return Response({
                        "error": "No valid questions could be created for this exam"
                    }, status=status.HTTP_400_BAD_REQUEST)

                # استخدام Response Serializer
                response_data = {
                    "exam_id": exam.id,
                    "questions_count": questions_created,
                    "duration_minutes": duration,
                    "message": "Exam created successfully"
                }
                response_serializer = GenerateExamResponseSerializer(response_data)
                
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({
                "error": f"Failed to create exam: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GetExamView(APIView):
    permission_classes = []  # إضافة هذا السطر
    authentication_classes = []    
    def get(self, request, exam_id):
        try:
            exam = Exam.objects.select_related('book', 'student').get(
                id=exam_id, 
                student=request.user
            )
        except Exam.DoesNotExist:
            return Response({"error": "Exam not found"}, status=status.HTTP_404_NOT_FOUND)

        # التحقق من انتهاء الوقت
        if exam.is_finished:
            return Response({
                "error": "Exam is already finished",
                "exam_id": exam.id,
                "score": exam.score
            }, status=status.HTTP_400_BAD_REQUEST)

        # حساب الوقت المتبقي
        time_elapsed = (timezone.now() - exam.start_time).total_seconds() / 60
        time_remaining = max(0, exam.duration_minutes - time_elapsed)
        
        if time_remaining <= 0:
            # إنهاء الامتحان تلقائياً
            exam.is_finished = True
            exam.end_time = timezone.now()
            exam.save()
            return Response({
                "error": "Exam time has expired",
                "exam_id": exam.id
            }, status=status.HTTP_400_BAD_REQUEST)

        # استخدام ExamDetailSerializer لإرجاع البيانات
        serializer = ExamDetailSerializer(exam)
        return Response(serializer.data)


class SubmitExamView(APIView):
    permission_classes = []  # إضافة هذا السطر
    authentication_classes = []
    
    def post(self, request, exam_id):
        # التحقق من صحة البيانات المرسلة
        request_serializer = SubmitExamRequestSerializer(data=request.data)
        if not request_serializer.is_valid():
            return Response(request_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            exam = Exam.objects.select_related('student').get(
                id=exam_id, 
                student=request.user
            )
        except Exam.DoesNotExist:
            return Response({"error": "Exam not found"}, status=status.HTTP_404_NOT_FOUND)

        if exam.is_finished:
            return Response({
                "error": "Exam already submitted",
                "score": exam.score
            }, status=status.HTTP_400_BAD_REQUEST)

        answers = request_serializer.validated_data['answers']

        try:
            with transaction.atomic():
                total_score = 0
                total_points = 0
                correct_count = 0
                processed_questions = []

                exam_questions = {eq.id: eq for eq in exam.exam_questions.all()}

                for ans in answers:
                    question_id = ans["question_id"]
                    if question_id not in exam_questions:
                        continue

                    eq = exam_questions[question_id]
                    student_answer = ans["answer"]
                    
                    if student_answer is None:
                        continue

                    eq.student_answer = student_answer

                    # تصحيح بناءً على نوع السؤال
                    is_correct = self._check_answer(eq, student_answer)
                    eq.is_correct = is_correct

                    total_points += float(eq.points)
                    if is_correct:
                        total_score += float(eq.points)
                        correct_count += 1

                    eq.save()
                    processed_questions.append(eq.id)

                # تسجيل الأسئلة غير المجابة كخطأ
                for eq in exam_questions.values():
                    if eq.id not in processed_questions:
                        eq.student_answer = None
                        eq.is_correct = False
                        eq.save()

                # حساب النتيجة النهائية
                if total_points > 0:
                    percentage_score = (total_score / total_points) * 100
                    exam.score = round(percentage_score, 2)
                else:
                    exam.score = 0

                exam.is_finished = True
                exam.end_time = timezone.now()
                exam.save()

                # استخدام Response Serializer
                response_data = {
                    "exam_id": exam.id,
                    "score": exam.score,
                    "total_points": total_points,
                    "earned_points": total_score,
                    "correct_answers": correct_count,
                    "total_questions": len(exam_questions),
                    "message": "Exam submitted successfully"
                }
                response_serializer = SubmitExamResponseSerializer(response_data)
                
                return Response(response_serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "error": f"Failed to submit exam: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _check_answer(self, exam_question, student_answer):
        """فحص إجابة الطالب بناءً على نوع السؤال"""
        question_type = exam_question.question_type
        correct_answer = exam_question.correct_answer

        if question_type == "mcq":
            if isinstance(correct_answer, dict) and 'answer_id' in correct_answer:
                return str(student_answer) == str(correct_answer['answer_id'])
            else:
                return student_answer == correct_answer

        elif question_type == "truefalse":
            if isinstance(student_answer, str):
                student_bool = student_answer.lower() in ["true", "1", "صح", "صحيح", "نعم"]
            else:
                student_bool = bool(student_answer)
            
            if isinstance(correct_answer, dict) and 'answer' in correct_answer:
                return student_bool == correct_answer['answer']
            else:
                return student_bool == correct_answer

        elif question_type == "matching":
            if isinstance(correct_answer, dict) and 'matches' in correct_answer:
                correct_matches = correct_answer['matches']
            else:
                correct_matches = correct_answer
            
            return isinstance(student_answer, dict) and student_answer == correct_matches

        elif question_type == "reading":
            if isinstance(correct_answer, dict) and 'answer' in correct_answer:
                return student_answer == correct_answer['answer']
            else:
                return student_answer == correct_answer

        return False


class ExamResultView(APIView):
    permission_classes = []  # إضافة هذا السطر
    authentication_classes = []
    
    def get(self, request, exam_id):
        try:
            exam = Exam.objects.select_related('book', 'student').get(
                id=exam_id, 
                student=request.user
            )
        except Exam.DoesNotExist:
            return Response({"error": "Exam not found"}, status=status.HTTP_404_NOT_FOUND)

        if not exam.is_finished:
            return Response({
                "error": "Exam is not finished yet",
                "exam_id": exam.id
            }, status=status.HTTP_400_BAD_REQUEST)

        # استخدام ExamResultSerializer لإرجاع البيانات
        serializer = ExamResultSerializer(exam)
        return Response(serializer.data)


class StudentExamsView(APIView):
    permission_classes = []  # إضافة هذا السطر
    authentication_classes = []
    
    def get(self, request):
        """جلب قائمة امتحانات الطالب"""
        exams = Exam.objects.filter(
            student=request.user
        ).select_related('book').order_by('-start_time')
        
        # استخدام Serializer لتنسيق البيانات
        serializer = ExamSerializer(exams, many=True)
        
        response_data = {
            "exams": serializer.data,
            "total_exams": exams.count()
        }
        
        response_serializer = StudentExamsListSerializer(response_data)
        return Response(response_serializer.data)


# Views إضافية للإدارة والمدرسين (اختيارية)
class ExamAdminListView(APIView):
    """View للمدرسين/الإدارة لرؤية جميع الامتحانات"""
    permission_classes = []  # إضافة هذا السطر
    authentication_classes = []  # يمكن إضافة IsAdminUser أو IsTeacher
    
    def get(self, request):
        """جلب جميع الامتحانات مع فلترة حسب المعايير"""
        exams = Exam.objects.select_related('student', 'book').all()
        
        # فلترة حسب المعايير
        book_id = request.query_params.get('book_id')
        student_id = request.query_params.get('student_id')
        is_finished = request.query_params.get('is_finished')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        if book_id:
            exams = exams.filter(book_id=book_id)
        if student_id:
            exams = exams.filter(student_id=student_id)
        if is_finished is not None:
            exams = exams.filter(is_finished=is_finished.lower() == 'true')
        if date_from:
            exams = exams.filter(start_time__date__gte=date_from)
        if date_to:
            exams = exams.filter(start_time__date__lte=date_to)
        
        # ترتيب النتائج
        ordering = request.query_params.get('ordering', '-start_time')
        exams = exams.order_by(ordering)
        
        # Pagination (يمكن استخدام PageNumberPagination)
        from rest_framework.pagination import PageNumberPagination
        
        paginator = PageNumberPagination()
        paginator.page_size = 20
        paginated_exams = paginator.paginate_queryset(exams, request)
        
        from .serializers import ExamAdminSerializer
        serializer = ExamAdminSerializer(paginated_exams, many=True)
        
        return paginator.get_paginated_response(serializer.data)


class ExamStatisticsView(APIView):
    """View للحصول على إحصائيات شاملة للامتحانات"""
    permission_classes = []  # إضافة هذا السطر
    authentication_classes = []
    
    def get(self, request):
        """إحصائيات عامة للطالب أو للنظام"""
        user = request.user
        
        # إحصائيات الطالب
        if not user.is_staff:  # طالب عادي
            exams = Exam.objects.filter(student=user, is_finished=True)
            
            if not exams.exists():
                return Response({
                    "message": "No completed exams found",
                    "statistics": {}
                })
            
            # حساب الإحصائيات
            total_exams = exams.count()
            avg_score = exams.aggregate(
                avg_score=models.Avg('score')
            )['avg_score'] or 0
            
            highest_score = exams.aggregate(
                max_score=models.Max('score')
            )['max_score'] or 0
            
            lowest_score = exams.aggregate(
                min_score=models.Min('score')
            )['min_score'] or 0
            
            # إحصائيات حسب الكتاب
            from django.db.models import Count, Avg
            books_stats = exams.values('book__title').annotate(
                exam_count=Count('id'),
                avg_score=Avg('score')
            ).order_by('-avg_score')
            
            # إحصائيات الأداء الشهرية
            from django.db.models.functions import TruncMonth
            monthly_stats = exams.annotate(
                month=TruncMonth('start_time')
            ).values('month').annotate(
                exam_count=Count('id'),
                avg_score=Avg('score')
            ).order_by('month')
            
            statistics = {
                "total_exams": total_exams,
                "average_score": round(avg_score, 2),
                "highest_score": highest_score,
                "lowest_score": lowest_score,
                "books_performance": list(books_stats),
                "monthly_performance": [
                    {
                        "month": stat['month'].strftime("%Y-%m"),
                        "exam_count": stat['exam_count'],
                        "avg_score": round(stat['avg_score'], 2)
                    }
                    for stat in monthly_stats
                ]
            }
            
            return Response({
                "student_name": user.get_full_name() or user.username,
                "statistics": statistics
            })
        
        else:  # مدرس أو إدارة - إحصائيات عامة للنظام
            from django.db.models import Count, Avg
            
            total_exams = Exam.objects.count()
            finished_exams = Exam.objects.filter(is_finished=True).count()
            active_exams = total_exams - finished_exams
            
            avg_score = Exam.objects.filter(
                is_finished=True
            ).aggregate(avg_score=Avg('score'))['avg_score'] or 0
            
            # أكثر الكتب امتحاناً
            popular_books = Exam.objects.values('book__title').annotate(
                exam_count=Count('id')
            ).order_by('-exam_count')[:10]
            
            # أداء الطلاب
            top_students = Exam.objects.filter(
                is_finished=True
            ).values('student__username', 'student__first_name', 'student__last_name').annotate(
                exam_count=Count('id'),
                avg_score=Avg('score')
            ).order_by('-avg_score')[:10]
            
            statistics = {
                "total_exams": total_exams,
                "finished_exams": finished_exams,
                "active_exams": active_exams,
                "overall_average_score": round(avg_score, 2),
                "popular_books": list(popular_books),
                "top_students": [
                    {
                        "username": student['student__username'],
                        "name": f"{student['student__first_name']} {student['student__last_name']}".strip() or student['student__username'],
                        "exam_count": student['exam_count'],
                        "avg_score": round(student['avg_score'], 2)
                    }
                    for student in top_students
                ]
            }
            
            return Response({
                "system_statistics": statistics
            })


# Utility Views
class ExamHealthCheckView(APIView):
    """فحص حالة الامتحانات المعلقة وتنظيفها"""
    permission_classes = []  # إضافة هذا السطر
    authentication_classes = []  # يمكن تقييدها للإدارة فقط
    
    def post(self, request):
        """تنظيف الامتحانات المنتهية الصلاحية"""
        from django.utils import timezone
        
        # البحث عن الامتحانات المنتهية الصلاحية وغير المكتملة
        expired_exams = Exam.objects.filter(
            is_finished=False,
            start_time__lt=timezone.now() - timezone.timedelta(hours=6)  # 6 ساعات كحد أقصى
        )
        
        updated_count = 0
        for exam in expired_exams:
            # حساب إذا كان الوقت انتهى فعلاً
            time_elapsed = (timezone.now() - exam.start_time).total_seconds() / 60
            if time_elapsed > exam.duration_minutes:
                exam.is_finished = True
                exam.end_time = exam.start_time + timezone.timedelta(minutes=exam.duration_minutes)
                exam.save()
                updated_count += 1
        
        return Response({
            "message": f"Updated {updated_count} expired exams",
            "updated_exams": updated_count
        })


# ViewSet alternative (اختياري)
from rest_framework import viewsets, mixins
from rest_framework.decorators import action

class ExamViewSet(mixins.ListModelMixin,
                  mixins.RetrieveModelMixin,
                  viewsets.GenericViewSet):
    """ViewSet شامل للامتحانات (بديل للـ APIViews)"""
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Exam.objects.filter(student=self.request.user).select_related('book')
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ExamDetailSerializer
        elif self.action == 'results':
            return ExamResultSerializer
        return ExamSerializer
    
    @action(detail=True, methods=['get'])
    def results(self, request, pk=None):
        """الحصول على نتائج امتحان محدد"""
        exam = self.get_object()
        if not exam.is_finished:
            return Response({
                "error": "Exam is not finished yet"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = self.get_serializer(exam)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """إحصائيات الطالب"""
        # يمكن استخدام نفس منطق ExamStatisticsView
        pass