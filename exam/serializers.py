from rest_framework import serializers
from .models import Exam, ExamQuestion
from questions.models import MCQQuestion, MCQChoice, MatchingQuestion, MatchingPair, TrueFalseQuestion, ReadingComprehension
from questions.serializers import MCQQuestionSerializer, MatchingQuestionSerializer, TrueFalseQuestionSerializer, ReadingComprehensionSerializer

class ExamQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamQuestion
        fields = "__all__"


class ExamSerializer(serializers.ModelSerializer):
    exam_questions = serializers.SerializerMethodField()

    class Meta:
        model = Exam
        fields = ["id", "book", "difficulty", "duration_minutes", "exam_questions"]

    def get_exam_questions(self, obj):
        result = []
        for eq in obj.exam_questions.all():
            if eq.question_type == "mcq":
                question = MCQQuestion.objects.get(id=eq.question_id)
                result.append(MCQQuestionSerializer(question).data)
            elif eq.question_type == "matching":
                question = MatchingQuestion.objects.get(id=eq.question_id)
                result.append(MatchingQuestionSerializer(question).data)
            elif eq.question_type == "truefalse":
                question = TrueFalseQuestion.objects.get(id=eq.question_id)
                result.append(TrueFalseQuestionSerializer(question).data)
            elif eq.question_type == "reading":
                question = ReadingComprehension.objects.get(id=eq.question_id)
                result.append(ReadingComprehensionSerializer(question).data)
        return result