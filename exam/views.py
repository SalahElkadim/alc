from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
import random
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import Exam, ExamQuestion,ExamResult
from questions.models import MCQQuestion, MatchingQuestion, TrueFalseQuestion, ReadingComprehension
from .serializers import ExamSerializer,ExamResultSerializer
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import json


class GenerateExamAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        book_id = request.data.get("book")
        difficulty = request.data.get("difficulty")

        if not book_id or not difficulty:
            return Response({"error_message": "book and difficulty are required"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            try:
                exam = Exam.objects.create(
                    student=request.user,
                    book_id=book_id,
                    duration_minutes=30
                )

                # جلب الأسئلة مع التحقق من وجودها
                mcqs = list(MCQQuestion.objects.filter(book_id=book_id, difficulty=difficulty))
                matches = list(MatchingQuestion.objects.filter(book_id=book_id, difficulty=difficulty))
                tfs = list(TrueFalseQuestion.objects.filter(book_id=book_id, difficulty=difficulty))
                readings = list(ReadingComprehension.objects.filter(book_id=book_id, difficulty=difficulty))

                # التحقق من وجود أسئلة كافية
                required_count = 5
                if len(mcqs) < required_count or len(matches) < required_count or \
                   len(tfs) < required_count or len(readings) < required_count:
                    return Response({
                        "error_message": "عدد الأسئلة غير كافي لإنشاء الامتحان",
                        "available": {
                            "mcqs": len(mcqs),
                            "matches": len(matches),
                            "tfs": len(tfs),
                            "readings": len(readings)
                        },
                        "required": required_count
                    }, status=status.HTTP_400_BAD_REQUEST)

                # خلط الأسئلة
                random.shuffle(mcqs)
                random.shuffle(matches)
                random.shuffle(tfs)
                random.shuffle(readings)

                # اختيار الأسئلة
                selected_mcqs = mcqs[:required_count]
                selected_matches = matches[:required_count]
                selected_tfs = tfs[:required_count]
                selected_readings = readings[:required_count]

                # إنشاء أسئلة MCQ
                for q in selected_mcqs:
                    ExamQuestion.objects.create(
                        exam=exam,
                        question_type="mcq",
                        question_id=q.id,
                        question_text=q.text,
                        correct_answer=q.correct_answer,
                        points=1
                    )

                # إنشاء أسئلة المطابقة
                for q in selected_matches:
                    pairs_data = []
                    for pair in q.pairs.all():
                        pairs_data.append({
                            "match_key": pair.match_key,
                            "left_item": pair.left_item,
                            "right_item": pair.right_item
                        })
                    
                    # حساب النقاط بناءً على عدد المطابقات
                    points = len(pairs_data) if pairs_data else 1
                    
                    ExamQuestion.objects.create(
                        exam=exam,
                        question_type="matching",
                        question_id=q.id,
                        question_text=q.text,
                        correct_answer=pairs_data,
                        points=points  # نقطة لكل مطابقة
                    )

                # إنشاء أسئلة صح/خطأ
                for q in selected_tfs:
                    ExamQuestion.objects.create(
                        exam=exam,
                        question_type="truefalse",
                        question_id=q.id,
                        question_text=q.text,
                        correct_answer=q.is_true,
                        points=1
                    )

                # إنشاء أسئلة القراءة مع حساب النقاط الصحيح
                for q in selected_readings:
                    reading_questions = []
                    
                    if hasattr(q, 'questions_data') and q.questions_data:
                        if isinstance(q.questions_data, list):
                            for item in q.questions_data:
                                if isinstance(item, dict):
                                    formatted_question = {
                                        "question": item.get("question", ""),
                                        "correct_answer": item.get("correct_answer", ""),
                                        "choices": item.get("choices", []) if item.get("type") == "mcq" else []
                                    }
                                    reading_questions.append(formatted_question)
                    
                    # حساب النقاط بناءً على عدد الأسئلة الفرعية
                    points = len(reading_questions) if reading_questions else 1
                    
                    ExamQuestion.objects.create(
                        exam=exam,
                        question_type="reading",
                        question_id=q.id,
                        question_text=q.title,
                        correct_answer=reading_questions,
                        points=points  # نقطة لكل سؤال فرعي
                    )

                return Response(ExamSerializer(exam).data, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                return Response({
                    "error_message": f"خطأ في إنشاء الامتحان: {str(e)}"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SubmitExamAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            exam_id = request.data.get("exam_id")
            answers = request.data.get("answers", [])

            # التحقق من وجود البيانات المطلوبة
            if not exam_id:
                return Response({
                    "success": False,
                    "error_message": "exam_id مطلوب"
                }, status=status.HTTP_400_BAD_REQUEST)

            if not isinstance(answers, list):
                return Response({
                    "success": False,
                    "error_message": "answers يجب أن تكون قائمة"
                }, status=status.HTTP_400_BAD_REQUEST)


            # جلب الامتحان والتحقق من صحته
            try:
                exam = Exam.objects.get(id=exam_id, student=request.user)
            except Exam.DoesNotExist:
                return Response({
                    "success": False,
                    "error_message": "الامتحان غير موجود أو غير مخصص لك"
                }, status=status.HTTP_404_NOT_FOUND)

            # التحقق من أن الامتحان لم ينته بعد
            if exam.is_finished:
                return Response({
                    "success": False,
                    "error_message": "تم تقديم هذا الامتحان مسبقاً"
                }, status=status.HTTP_400_BAD_REQUEST)

            # جلب جميع أسئلة الامتحان
            exam_questions = exam.exam_questions.all()
            
            if not exam_questions.exists():
                return Response({
                    "success": False,
                    "error_message": "لا توجد أسئلة في هذا الامتحان"
                }, status=status.HTTP_400_BAD_REQUEST)

            # معالجة الإجابات وحساب الدرجات
            total_score = Decimal('0')
            total_possible = Decimal('0')
            detailed_results = []

            with transaction.atomic():
                # تحويل الإجابات إلى قاموس للوصول السريع
                answers_dict = {}
                for answer_item in answers:
                    public_q_id = answer_item.get('question_id')
                    if public_q_id:
                        answers_dict[public_q_id] = answer_item

                # معالجة كل سؤال
                for exam_question in exam_questions:
                    student_answer_data = answers_dict.get(str(exam_question.public_id))
                    question_result = {
                        "question_id": str(exam_question.public_id),
                        "original_question_id": exam_question.question_id,
                        "question_type": exam_question.question_type,
                        "question_text": exam_question.question_text,
                    }
                    
                    if student_answer_data:
                        student_answer = student_answer_data.get('answer')
                        question_type = exam_question.question_type

                        # حفظ إجابة الطالب
                        exam_question.student_answer = student_answer

                        # تصحيح السؤال حسب نوعه
                        if question_type == 'mcq':
                            score = self._grade_mcq(exam_question, student_answer)
                            total_score += score
                            total_possible += exam_question.points
                            
                            question_result.update({
                                "student_answer": student_answer,
                                "correct_answer": exam_question.correct_answer,
                                "is_correct": exam_question.is_correct,
                                "points_earned": float(score),
                                "points_possible": float(exam_question.points)
                            })

                        elif question_type == 'truefalse':
                            score = self._grade_truefalse(exam_question, student_answer)
                            total_score += score
                            total_possible += exam_question.points
                            
                            question_result.update({
                                "student_answer": student_answer,
                                "correct_answer": exam_question.correct_answer,
                                "is_correct": exam_question.is_correct,
                                "points_earned": float(score),
                                "points_possible": float(exam_question.points)
                            })

                        elif question_type == 'matching':
                            score, possible_points = self._grade_matching(exam_question, student_answer)
                            total_score += score
                            total_possible += possible_points
                            
                            question_result.update({
                                "student_answer": student_answer,
                                "correct_answer": exam_question.correct_answer,
                                "is_correct": exam_question.is_correct,
                                "points_earned": float(score),
                                "points_possible": float(possible_points),
                                "partial_credit": True if score > 0 and score < possible_points else False
                            })

                        elif question_type == 'reading':
                            score, possible_points = self._grade_reading(exam_question, student_answer)
                            total_score += score
                            total_possible += possible_points
                            
                            question_result.update({
                                "student_answer": student_answer,
                                "correct_answer": exam_question.correct_answer,
                                "is_correct": exam_question.is_correct,
                                "points_earned": float(score),
                                "points_possible": float(possible_points),
                                "sub_questions_count": int(possible_points),
                                "partial_credit": True if score > 0 and score < possible_points else False
                            })

                        exam_question.save()
                        
                    else:
                        # لم يجب على السؤال
                        possible_points = exam_question.points
                        total_possible += possible_points
                        exam_question.is_correct = False
                        exam_question.save()
                        
                        question_result.update({
                            "student_answer": None,
                            "correct_answer": exam_question.correct_answer,
                            "is_correct": False,
                            "points_earned": 0,
                            "points_possible": float(possible_points),
                            "error_message": "لم يتم الإجابة على هذا السؤال"
                        })
                    
                    detailed_results.append(question_result)

                # حساب النسبة المئوية
                percentage = float((total_score / total_possible * 100) if total_possible > 0 else 0)

                # تحديد التقدير
                grade = self._get_letter_grade(percentage)

                # تحديث بيانات الامتحان
                exam.score = total_score
                exam.is_finished = True
                exam.end_time = timezone.now()
                exam.save()
                ExamResult.objects.create(
                    exam=exam,
                    student=request.user,
                    book=exam.book,
                    score=total_score,
                    percentage=Decimal(str(percentage)),
                    letter_grade=grade
                )

                return Response({
                    "success": True,
                    "exam_id": exam.id,
                    "total_score": float(total_score),
                    "total_possible": float(total_possible),
                    "percentage": round(percentage, 2),
                    "letter_grade": grade,
                    "questions_count": len(exam_questions),
                    "detailed_results": detailed_results,
                    "grading_summary": {
                        "mcq_questions": len([q for q in detailed_results if q["question_type"] == "mcq"]),
                        "truefalse_questions": len([q for q in detailed_results if q["question_type"] == "truefalse"]),
                        "matching_questions": len([q for q in detailed_results if q["question_type"] == "matching"]),
                        "reading_questions": len([q for q in detailed_results if q["question_type"] == "reading"])
                    },
                    "message": "تم تقديم الامتحان بنجاح"
                }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "success": False,
                "error_message": f"خطأ في معالجة الامتحان: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _grade_mcq(self, exam_question, student_answer):
        """تصحيح سؤال الاختيار المتعدد"""
        if not student_answer:
            exam_question.is_correct = False
            return Decimal('0')

        correct_answer = exam_question.correct_answer
        # تطهير الإجابات للمقارنة الصحيحة
        student_clean = str(student_answer).strip().lower()
        correct_clean = str(correct_answer).strip().lower()
        
        is_correct = student_clean == correct_clean
        exam_question.is_correct = is_correct
        return exam_question.points if is_correct else Decimal('0')

    def _grade_truefalse(self, exam_question, student_answer):
        """تصحيح سؤال صح/خطأ"""
        if student_answer is None:
            exam_question.is_correct = False
            return Decimal('0')

        correct_answer = exam_question.correct_answer
        
        # معالجة الإجابات المختلفة (true/false, 1/0, "true"/"false")
        if isinstance(student_answer, str):
            student_answer = student_answer.lower().strip()
            if student_answer in ['true', '1', 'yes', 'صح']:
                student_answer = True
            elif student_answer in ['false', '0', 'no', 'خطأ']:
                student_answer = False
        
        is_correct = bool(student_answer) == bool(correct_answer)
        exam_question.is_correct = is_correct
        return exam_question.points if is_correct else Decimal('0')

    def _grade_matching(self, exam_question, student_answer):
        """تصحيح سؤال المطابقة مع نقاط جزئية"""
        if not student_answer or not isinstance(student_answer, list):
            exam_question.is_correct = False
            return Decimal('0'), exam_question.points

        correct_pairs = exam_question.correct_answer
        if not isinstance(correct_pairs, list) or not correct_pairs:
            exam_question.is_correct = False
            return Decimal('0'), exam_question.points

        # تحويل الإجابات الصحيحة إلى قاموس
        correct_dict = {}
        for pair in correct_pairs:
            if isinstance(pair, dict) and 'left_item' in pair and 'right_item' in pair:
                left = str(pair['left_item']).strip().lower()
                right = str(pair['right_item']).strip().lower()
                correct_dict[left] = right

        # تحويل إجابات الطالب إلى قاموس
        student_dict = {}
        for pair in student_answer:
            if isinstance(pair, dict) and 'left_item' in pair and 'right_item' in pair:
                left = str(pair['left_item']).strip().lower()
                right = str(pair['right_item']).strip().lower()
                student_dict[left] = right

        # حساب النقاط الجزئية
        correct_matches = 0
        total_pairs = len(correct_dict)
        
        for left_item, correct_right in correct_dict.items():
            if left_item in student_dict and student_dict[left_item] == correct_right:
                correct_matches += 1

        # حساب النقاط بناءً على النسبة الصحيحة
        if total_pairs == 0:
            exam_question.is_correct = False
            return Decimal('0'), Decimal('1')
        
        score = Decimal(str(correct_matches))
        total_possible = Decimal(str(total_pairs))
        
        # يعتبر السؤال صحيح إذا كانت كل المطابقات صحيحة
        exam_question.is_correct = (correct_matches == total_pairs)
        
        return score, total_possible

    def _grade_reading(self, exam_question, student_answer):
        """تصحيح أسئلة القراءة مع نقاط جزئية"""
        reading_questions = exam_question.correct_answer
        
        if not isinstance(reading_questions, list) or not reading_questions:
            exam_question.is_correct = False
            return Decimal('0'), Decimal('1')

        total_sub_questions = len(reading_questions)
        
        # التحقق من وجود إجابة الطالب
        if not student_answer:
            exam_question.is_correct = False
            return Decimal('0'), Decimal(str(total_sub_questions))

        # حساب النقاط
        correct_count = 0
        
        # إذا كانت إجابة الطالب عبارة عن نص واحد (الحالة الحالية)
        if isinstance(student_answer, str):
            # نفترض أن هناك سؤال واحد فقط في أسئلة القراءة
            if len(reading_questions) == 1:
                q_data = reading_questions[0]
                if isinstance(q_data, dict) and 'correct_answer' in q_data:
                    correct_answer = str(q_data['correct_answer']).strip().lower()
                    student_ans = str(student_answer).strip().lower()
                    
                    if correct_answer == student_ans:
                        correct_count = 1
            
            # حفظ النتيجة
            exam_question.is_correct = (correct_count == total_sub_questions)
            return Decimal(str(correct_count)), Decimal(str(total_sub_questions))
        
        # إذا كانت إجابة الطالب عبارة عن list (للمستقبل)
        elif isinstance(student_answer, list):
            # تحويل أسئلة القراءة إلى قاموس للوصول السريع
            correct_answers = {}
            for i, q_data in enumerate(reading_questions):
                if isinstance(q_data, dict) and 'question' in q_data and 'correct_answer' in q_data:
                    question_text = str(q_data['question']).strip().lower()
                    correct_answer = str(q_data['correct_answer']).strip().lower()
                    # استخدم الفهرس كمفتاح احتياطي إذا كانت الأسئلة متشابهة
                    key = f"{question_text}_{i}"
                    correct_answers[key] = correct_answer
                    # أضف المفتاح بدون فهرس أيضاً
                    if question_text not in correct_answers:
                        correct_answers[question_text] = correct_answer
            
            for i, student_q in enumerate(student_answer):
                if isinstance(student_q, dict) and 'question' in student_q and 'answer' in student_q:
                    question_text = str(student_q['question']).strip().lower()
                    student_ans = str(student_q['answer']).strip().lower()

                    # جرب البحث بالفهرس أولاً، ثم بدونه
                    key_with_index = f"{question_text}_{i}"
                    
                    if key_with_index in correct_answers:
                        if correct_answers[key_with_index] == student_ans:
                            correct_count += 1
                    elif question_text in correct_answers:
                        if correct_answers[question_text] == student_ans:
                            correct_count += 1

            # حفظ النتيجة
            exam_question.is_correct = (correct_count == total_sub_questions)
            return Decimal(str(correct_count)), Decimal(str(total_sub_questions))
        
        # حالة أخرى غير متوقعة
        else:
            exam_question.is_correct = False
            return Decimal('0'), Decimal(str(total_sub_questions))

    def _get_letter_grade(self, percentage):
        """تحديد التقدير بناء على النسبة المئوية"""
        if percentage >= 90:
            return "A"
        elif percentage >= 80:
            return "B"
        elif percentage >= 70:
            return "C"
        elif percentage >= 60:
            return "D"
        else:
            return "F"
            
class ExamResultListAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        results = ExamResult.objects.filter(student=request.user).order_by("-created_at")
        serializer = ExamResultSerializer(results, many=True)
        return Response(serializer.data)