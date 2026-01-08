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
        total_required = 20

        if not book_id or not difficulty:
            return Response({"error_message": "book and difficulty are required"}, 
                            status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            try:
                exam = Exam.objects.create(
                    student=request.user,
                    book_id=book_id,
                    duration_minutes=30
                )

                # *********** 1) Fetch questions from the requested difficulty level first ***********
                mcqs = list(MCQQuestion.objects.filter(book_id=book_id, difficulty=difficulty))
                matches = list(MatchingQuestion.objects.filter(book_id=book_id, difficulty=difficulty))
                tfs = list(TrueFalseQuestion.objects.filter(book_id=book_id, difficulty=difficulty))
                readings = list(ReadingComprehension.objects.filter(book_id=book_id, difficulty=difficulty))

                total_first_level = len(mcqs) + len(matches) + len(tfs) + len(readings)

                # *********** 2) If not enough questions → get from other difficulty levels ***********
                if total_first_level < total_required:
                    remaining = total_required - total_first_level

                    other_levels = ["easy", "medium", "hard"]
                    if difficulty in other_levels:
                        other_levels.remove(difficulty)

                    extra_mcqs = list(MCQQuestion.objects.filter(book_id=book_id, difficulty__in=other_levels))
                    extra_matches = list(MatchingQuestion.objects.filter(book_id=book_id, difficulty__in=other_levels))
                    extra_tfs = list(TrueFalseQuestion.objects.filter(book_id=book_id, difficulty__in=other_levels))
                    extra_readings = list(ReadingComprehension.objects.filter(book_id=book_id, difficulty__in=other_levels))

                    extra_questions = {
                        "mcq": extra_mcqs,
                        "matching": extra_matches,
                        "truefalse": extra_tfs,
                        "reading": extra_readings
                    }

                    for key in extra_questions:
                        random.shuffle(extra_questions[key])

                    for key, qs in extra_questions.items():
                        if remaining <= 0:
                            break

                        take = qs[:remaining]

                        if key == "mcq":
                            mcqs += take
                        elif key == "matching":
                            matches += take
                        elif key == "truefalse":
                            tfs += take
                        elif key == "reading":
                            readings += take

                        remaining -= len(take)

                # *********** 3) If still not enough questions → insufficient questions available ***********
                total_available = len(mcqs) + len(matches) + len(tfs) + len(readings)
                if total_available < total_required:
                    return Response({
                        "error_message": "Not enough questions available across all difficulty levels",
                        "available": total_available,
                        "required": total_required
                    }, status=status.HTTP_400_BAD_REQUEST)

                # *********** 4) Shuffle and combine all questions ***********
                random.shuffle(mcqs)
                random.shuffle(matches)
                random.shuffle(tfs)
                random.shuffle(readings)

                combined_questions = []
                combined_questions += [("mcq", q) for q in mcqs]
                combined_questions += [("matching", q) for q in matches]
                combined_questions += [("truefalse", q) for q in tfs]
                combined_questions += [("reading", q) for q in readings]

                random.shuffle(combined_questions)

                selected = combined_questions[:total_required]

                # *********** 5) Create exam questions ***********
                for qtype, q in selected:

                    if qtype == "mcq":
                        ExamQuestion.objects.create(
                            exam=exam,
                            question_type="mcq",
                            question_id=q.id,
                            question_text=q.text,
                            correct_answer=q.correct_answer,
                            points=1
                        )

                    elif qtype == "truefalse":
                        ExamQuestion.objects.create(
                            exam=exam,
                            question_type="truefalse",
                            question_id=q.id,
                            question_text=q.text,
                            correct_answer=q.is_true,
                            points=1
                        )

                    elif qtype == "matching":
                        pairs_data = [{
                            "match_key": p.match_key,
                            "left_item": p.left_item,
                            "right_item": p.right_item
                        } for p in q.pairs.all()]

                        ExamQuestion.objects.create(
                            exam=exam,
                            question_type="matching",
                            question_id=q.id,
                            question_text=q.text,
                            correct_answer=pairs_data,
                            points=max(1, len(pairs_data))
                        )

                    elif qtype == "reading":
                        reading_questions = []

                        if hasattr(q, 'questions_data') and isinstance(q.questions_data, list):
                            for item in q.questions_data:
                                if isinstance(item, dict):
                                    reading_questions.append({
                                        "question": item.get("question", ""),
                                        "correct_answer": item.get("correct_answer", ""),
                                        "choices": item.get("choices", []) if item.get("type") == "mcq" else []
                                    })

                        ExamQuestion.objects.create(
                            exam=exam,
                            question_type="reading",
                            question_id=q.id,
                            question_text=q.title,
                            correct_answer=reading_questions,
                            points=max(1, len(reading_questions))
                        )

                return Response(ExamSerializer(exam).data, status=status.HTTP_201_CREATED)

            except Exception as e:
                return Response({"error_message": str(e)},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SubmitExamAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            exam_id = request.data.get("exam_id")
            answers = request.data.get("answers", [])

            # Validate required data
            if not exam_id:
                return Response({
                    "success": False,
                    "error_message": "exam_id is required"
                }, status=status.HTTP_400_BAD_REQUEST)

            if not isinstance(answers, list):
                return Response({
                    "success": False,
                    "error_message": "answers must be a list"
                }, status=status.HTTP_400_BAD_REQUEST)


            # Fetch and validate exam
            try:
                exam = Exam.objects.get(id=exam_id, student=request.user)
            except Exam.DoesNotExist:
                return Response({
                    "success": False,
                    "error_message": "Exam not found or not assigned to you"
                }, status=status.HTTP_404_NOT_FOUND)

            # Check if exam is already finished
            if exam.is_finished:
                return Response({
                    "success": False,
                    "error_message": "This exam has already been submitted"
                }, status=status.HTTP_400_BAD_REQUEST)

            # Fetch all exam questions
            exam_questions = exam.exam_questions.all()
            
            if not exam_questions.exists():
                return Response({
                    "success": False,
                    "error_message": "No questions found in this exam"
                }, status=status.HTTP_400_BAD_REQUEST)

            # Process answers and calculate scores
            total_score = Decimal('0')
            total_possible = Decimal('0')
            detailed_results = []

            with transaction.atomic():
                # Convert answers to dictionary for quick access
                answers_dict = {}
                for answer_item in answers:
                    public_q_id = answer_item.get('question_id')
                    if public_q_id:
                        answers_dict[public_q_id] = answer_item

                # Process each question
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

                        # Save student answer
                        exam_question.student_answer = student_answer

                        # Grade question based on type
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
                        # Question not answered
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
                            "error_message": "This question was not answered"
                        })
                    
                    detailed_results.append(question_result)

                # Calculate percentage
                percentage = float((total_score / total_possible * 100) if total_possible > 0 else 0)

                # Determine letter grade
                grade = self._get_letter_grade(percentage)

                # Update exam data
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
                    "message": "Exam submitted successfully"
                }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "success": False,
                "error_message": f"Error processing exam: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _grade_mcq(self, exam_question, student_answer):
        """Grade multiple choice question"""
        if not student_answer:
            exam_question.is_correct = False
            return Decimal('0')

        correct_answer = exam_question.correct_answer
        # Clean answers for proper comparison
        student_clean = str(student_answer).strip().lower()
        correct_clean = str(correct_answer).strip().lower()
        
        is_correct = student_clean == correct_clean
        exam_question.is_correct = is_correct
        return exam_question.points if is_correct else Decimal('0')

    def _grade_truefalse(self, exam_question, student_answer):
        """Grade true/false question"""
        if student_answer is None:
            exam_question.is_correct = False
            return Decimal('0')

        correct_answer = exam_question.correct_answer
        
        # Handle different answer formats (true/false, 1/0, "true"/"false")
        if isinstance(student_answer, str):
            student_answer = student_answer.lower().strip()
            if student_answer in ['true', '1', 'yes']:
                student_answer = True
            elif student_answer in ['false', '0', 'no']:
                student_answer = False
        
        is_correct = bool(student_answer) == bool(correct_answer)
        exam_question.is_correct = is_correct
        return exam_question.points if is_correct else Decimal('0')

    def _grade_matching(self, exam_question, student_answer):
        """Grade matching question with partial credit"""
        if not student_answer or not isinstance(student_answer, list):
            exam_question.is_correct = False
            return Decimal('0'), exam_question.points

        correct_pairs = exam_question.correct_answer
        if not isinstance(correct_pairs, list) or not correct_pairs:
            exam_question.is_correct = False
            return Decimal('0'), exam_question.points

        # Convert correct answers to dictionary
        correct_dict = {}
        for pair in correct_pairs:
            if isinstance(pair, dict) and 'left_item' in pair and 'right_item' in pair:
                left = str(pair['left_item']).strip().lower()
                right = str(pair['right_item']).strip().lower()
                correct_dict[left] = right

        # Convert student answers to dictionary
        student_dict = {}
        for pair in student_answer:
            if isinstance(pair, dict) and 'left_item' in pair and 'right_item' in pair:
                left = str(pair['left_item']).strip().lower()
                right = str(pair['right_item']).strip().lower()
                student_dict[left] = right

        # Calculate partial credit
        correct_matches = 0
        total_pairs = len(correct_dict)
        
        for left_item, correct_right in correct_dict.items():
            if left_item in student_dict and student_dict[left_item] == correct_right:
                correct_matches += 1

        # Calculate points based on correct percentage
        if total_pairs == 0:
            exam_question.is_correct = False
            return Decimal('0'), Decimal('1')
        
        score = Decimal(str(correct_matches))
        total_possible = Decimal(str(total_pairs))
        
        # Question is correct only if all matches are correct
        exam_question.is_correct = (correct_matches == total_pairs)
        
        return score, total_possible

    def _grade_reading(self, exam_question, student_answer):
        """Grade reading comprehension questions with partial credit"""
        reading_questions = exam_question.correct_answer
        
        if not isinstance(reading_questions, list) or not reading_questions:
            exam_question.is_correct = False
            return Decimal('0'), Decimal('1')

        total_sub_questions = len(reading_questions)
        
        # Check if student answer exists
        if not student_answer:
            exam_question.is_correct = False
            return Decimal('0'), Decimal(str(total_sub_questions))

        # Calculate points
        correct_count = 0
        
        # If student answer is a single string (current case)
        if isinstance(student_answer, str):
            # Assume there's only one question in reading comprehension
            if len(reading_questions) == 1:
                q_data = reading_questions[0]
                if isinstance(q_data, dict) and 'correct_answer' in q_data:
                    correct_answer = str(q_data['correct_answer']).strip().lower()
                    student_ans = str(student_answer).strip().lower()
                    
                    if correct_answer == student_ans:
                        correct_count = 1
            
            # Save result
            exam_question.is_correct = (correct_count == total_sub_questions)
            return Decimal(str(correct_count)), Decimal(str(total_sub_questions))
        
        # If student answer is a list (for future)
        elif isinstance(student_answer, list):
            # Convert reading questions to dictionary for quick access
            correct_answers = {}
            for i, q_data in enumerate(reading_questions):
                if isinstance(q_data, dict) and 'question' in q_data and 'correct_answer' in q_data:
                    question_text = str(q_data['question']).strip().lower()
                    correct_answer = str(q_data['correct_answer']).strip().lower()
                    # Use index as fallback key if questions are similar
                    key = f"{question_text}_{i}"
                    correct_answers[key] = correct_answer
                    # Add key without index as well
                    if question_text not in correct_answers:
                        correct_answers[question_text] = correct_answer
            
            for i, student_q in enumerate(student_answer):
                if isinstance(student_q, dict) and 'question' in student_q and 'answer' in student_q:
                    question_text = str(student_q['question']).strip().lower()
                    student_ans = str(student_q['answer']).strip().lower()

                    # Try searching with index first, then without
                    key_with_index = f"{question_text}_{i}"
                    
                    if key_with_index in correct_answers:
                        if correct_answers[key_with_index] == student_ans:
                            correct_count += 1
                    elif question_text in correct_answers:
                        if correct_answers[question_text] == student_ans:
                            correct_count += 1

            # Save result
            exam_question.is_correct = (correct_count == total_sub_questions)
            return Decimal(str(correct_count)), Decimal(str(total_sub_questions))
        
        # Other unexpected case
        else:
            exam_question.is_correct = False
            return Decimal('0'), Decimal(str(total_sub_questions))

    def _get_letter_grade(self, percentage):
        """Determine letter grade based on percentage"""
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