from rest_framework import serializers
from .models import Exam, ExamQuestion
from questions.models import (
    MCQQuestion, MatchingQuestion, TrueFalseQuestion, ReadingComprehension
)
from questions.serializers import (
    MCQQuestionSerializer, MatchingQuestionSerializer,
    TrueFalseQuestionSerializer, ReadingComprehensionSerializer
)
import random


class ExamQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamQuestion
        fields = ["public_id", "question_type", "question_text"]  # نخلي الـ frontend يشوف public_id فقط


class ExamSerializer(serializers.ModelSerializer):
    exam_questions = serializers.SerializerMethodField()

    class Meta:
        model = Exam
        fields = ["id", "book", "difficulty", "duration_minutes", "exam_questions"]

    def get_exam_questions(self, obj):
        result = []
        for eq in obj.exam_questions.all():
            question_data = None

            if eq.question_type == "mcq":
                question = MCQQuestion.objects.get(id=eq.question_id)
                question_data = MCQQuestionSerializer(question).data

            elif eq.question_type == "matching":
                question = MatchingQuestion.objects.get(id=eq.question_id)
                data = MatchingQuestionSerializer(question).data
                shuffled_data = data.copy()
                matching_pairs = shuffled_data.get("matching_pairs", [])

                # شفل القوائم بحيث الطالب مايعرفش الترتيب الأصلي
                if matching_pairs and isinstance(matching_pairs, list):
                    for pair in matching_pairs:
                        for key, value in pair.items():
                            if isinstance(value, list):
                                random.shuffle(value)
                question_data = shuffled_data

            elif eq.question_type == "truefalse":
                question = TrueFalseQuestion.objects.get(id=eq.question_id)
                question_data = TrueFalseQuestionSerializer(question).data

            elif eq.question_type == "reading":
                question = ReadingComprehension.objects.get(id=eq.question_id)
                question_data = ReadingComprehensionSerializer(question).data

            if question_data:
                # نضيف public_id عشان الفرونت يجاوب بيه
                question_data["public_id"] = str(eq.public_id)
                result.append(question_data)

        return result

from .models import ExamResult

class ExamResultSerializer(serializers.ModelSerializer):
    book_title = serializers.SerializerMethodField()

    class Meta:
        model = ExamResult
        fields = ["id", "exam", "student", "book_title", "score", "percentage", "letter_grade", "created_at"]

    def get_book_title(self, obj):
        return obj.book.title if obj.book else None
