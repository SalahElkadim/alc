from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
import random
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import Exam, ExamQuestion
from questions.models import MCQQuestion, MatchingQuestion, TrueFalseQuestion, ReadingComprehension
from .serializers import ExamSerializer
from django.shortcuts import get_object_or_404




class GenerateExamAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        book_id = request.data.get("book")
        difficulty = request.data.get("difficulty")

        if not book_id or not difficulty:
            return Response({"error": "book and difficulty are required"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            exam = Exam.objects.create(
                student=request.user,
                book_id=book_id,
                duration_minutes=30
            )

            mcqs = list(MCQQuestion.objects.filter(book_id=book_id, difficulty=difficulty))
            matches = list(MatchingQuestion.objects.filter(book_id=book_id, difficulty=difficulty))
            tfs = list(TrueFalseQuestion.objects.filter(book_id=book_id, difficulty=difficulty))
            readings = list(ReadingComprehension.objects.filter(book_id=book_id, difficulty=difficulty))

            random.shuffle(mcqs)
            random.shuffle(matches)
            random.shuffle(tfs)
            random.shuffle(readings)

            selected_mcqs = mcqs[:5]
            selected_matches = matches[:5]
            selected_tfs = tfs[:5]
            selected_readings = readings[:5]

            for q in selected_mcqs:
                ExamQuestion.objects.create(
                    exam=exam,
                    question_type="mcq",
                    question_id=q.id,
                    question_text=q.text,
                    correct_answer=q.correct_answer,
                    points=1
                )

            for q in selected_matches:
                ExamQuestion.objects.create(
                    exam=exam,
                    question_type="matching",
                    question_id=q.id,
                    question_text=q.text,
                    correct_answer=[{"match_key": p.match_key, "left_item": p.left_item, "right_item": p.right_item} for p in q.pairs.all()],
                    points=1
                )

            for q in selected_tfs:
                ExamQuestion.objects.create(
                    exam=exam,
                    question_type="truefalse",
                    question_id=q.id,
                    question_text=q.text,
                    correct_answer=q.is_true,
                    points=1
                )

            for q in selected_readings:
                ExamQuestion.objects.create(
                    exam=exam,
                    question_type="reading",
                    question_id=q.id,
                    question_text=q.title,
                    correct_answer=q.questions_data,
                    points=1
                )

        return Response(ExamSerializer(exam).data, status=status.HTTP_201_CREATED)


class SubmitExamAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        exam_id = request.data.get("exam_id")  # من البودي
        if not exam_id:
            return Response({"error": "exam_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            exam = Exam.objects.get(id=exam_id, student=request.user)
        except Exam.DoesNotExist:
            return Response({"error": "Exam not found"}, status=status.HTTP_404_NOT_FOUND)

        answers = request.data.get("answers", {})

        if not answers:
            return Response({"error": "Answers are required"}, status=status.HTTP_400_BAD_REQUEST)

        total_score = 0
        max_score = 0

        for eq in exam.exam_questions.all():
            max_score += eq.points
            student_answer = answers.get(str(eq.question_id))
 # لازم تبقى string عشان JSON

            if student_answer is None:
                continue  # الطالب ماجاوبش السؤال

            # مقارنة الإجابة حسب نوع السؤال
            if eq.question_type == "mcq":
                if str(student_answer).strip() == str(eq.correct_answer).strip():
                    total_score += eq.points

            elif eq.question_type == "truefalse":
                if bool(student_answer) == bool(eq.correct_answer):
                    total_score += eq.points

            elif eq.question_type == "matching":
                # هتقارن القايمة كلها (ممكن تطور حسب الشكل اللي عندك)
                if student_answer == eq.correct_answer:
                    total_score += eq.points

            elif eq.question_type == "reading":
                # لو عندك structure معقد لازم تقارن كل سؤال داخلي
                if student_answer == eq.correct_answer:
                    total_score += eq.points

        percentage = (total_score / max_score) * 100 if max_score > 0 else 0

        return Response({
            "exam_id": exam.id,
            "student": request.user.email,
            "score": total_score,
            "max_score": max_score,
            "percentage": round(percentage, 2)
        }, status=status.HTTP_200_OK)