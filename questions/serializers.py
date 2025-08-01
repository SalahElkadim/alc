from rest_framework import serializers
from .models import (
    MCQQuestion, MCQChoice,
    MatchingQuestion, MatchingPair,
    ReadingPassage, ReadingQuestion, ReadingChoice,
    TrueFalseQuestion,Book
)

# -----------------------------
class BookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = '__all__'
# Base Question Serializer
# -----------------------------
class BaseQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        fields = '__all__'
        abstract = True


# -----------------------------
# MCQ Question
# -----------------------------
class MCQChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = MCQChoice
        fields = ['id', 'text']


class MCQQuestionSerializer(serializers.ModelSerializer):
    mcq_choices = MCQChoiceSerializer(many=True, source = "choices")

    class Meta:
        model = MCQQuestion
        fields = ['id', 'book', 'text', 'correct_answer', 'mcq_choices']

    def validate_mcq_choices(self, value):
        if len(value) < 2:
            raise serializers.ValidationError("يجب أن يحتوي السؤال على خيارين على الأقل.")

        texts = [choice['text'].strip() for choice in value]
        if len(texts) != len(set(texts)):
            raise serializers.ValidationError("يجب ألا تتكرر نصوص الخيارات.")
        return value

    def create(self, validated_data):
        choices_data = validated_data.pop('choices') 
        question = MCQQuestion.objects.create(**validated_data)
        MCQChoice.objects.bulk_create([
            MCQChoice(question=question, **choice) for choice in choices_data
        ])
        return question

    def update(self, instance, validated_data):
        choices_data = validated_data.pop('choices', None) 
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if choices_data is not None:
            instance.mcq_choices.all().delete()
            MCQChoice.objects.bulk_create([
                MCQChoice(question=instance, **choice) for choice in choices_data
            ])
        return instance


# -----------------------------
# Matching Question
# -----------------------------
class MatchingPairSerializer(serializers.ModelSerializer):
    class Meta:
        model = MatchingPair
        fields = ['id', 'match_key', 'left_item', 'right_item']



class MatchingQuestionSerializer(serializers.ModelSerializer):
    matching_pairs = MatchingPairSerializer(many=True, source='pairs')  # ربط العلاقات صح

    class Meta:
        model = MatchingQuestion
        fields = ['id', 'book', 'text', 'matching_pairs']

    def validate_matching_pairs(self, value):
        if len(value) < 2:
            raise serializers.ValidationError("يجب أن يحتوي السؤال على زوجين على الأقل.")

        keys = [pair['match_key'].strip() for pair in value]
        if len(keys) != len(set(keys)):
            raise serializers.ValidationError("يجب ألا تتكرر المفاتيح.")
        return value

    def create(self, validated_data):
        pairs_data = validated_data.pop('pairs')  # استخدم الـ source الصحيح
        question = MatchingQuestion.objects.create(**validated_data)
        MatchingPair.objects.bulk_create([
            MatchingPair(question=question, **pair) for pair in pairs_data
        ])
        return question

    def update(self, instance, validated_data):
        pairs_data = validated_data.pop('pairs', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if pairs_data is not None:
            instance.pairs.all().delete()
            MatchingPair.objects.bulk_create([
                MatchingPair(question=instance, **pair) for pair in pairs_data
            ])
        return instance



# -----------------------------
# True/False Question
# -----------------------------
class TrueFalseQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrueFalseQuestion
        fields = ['id', 'book', 'text', 'is_true']


# -----------------------------
# Reading Question
# -----------------------------
class ReadingChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadingChoice
        fields = ['id', 'text']


class ReadingQuestionSerializer(serializers.ModelSerializer):
    reading_choices = ReadingChoiceSerializer(many=True, required=False)

    class Meta:
        model = ReadingQuestion
        fields = ['id', 'passage', 'text', 'correct_answer', 'reading_choices','book']

    def validate_reading_choices(self, value):
        if value:
            if len(value) < 2:
                raise serializers.ValidationError("يجب أن تحتوي الخيارات على اثنين على الأقل.")

            texts = [choice['text'].strip() for choice in value]
            if len(texts) != len(set(texts)):
                raise serializers.ValidationError("يجب ألا تتكرر نصوص الخيارات.")
        return value

    def create(self, validated_data):
        choices_data = validated_data.pop('reading_choices', [])
        question = ReadingQuestion.objects.create(**validated_data)
        if choices_data:
            ReadingChoice.objects.bulk_create([
                ReadingChoice(question=question, **choice) for choice in choices_data
            ])
        return question

    def update(self, instance, validated_data):
        choices_data = validated_data.pop('reading_choices', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if choices_data is not None:
            instance.reading_choices.all().delete()
            ReadingChoice.objects.bulk_create([
                ReadingChoice(question=instance, **choice) for choice in choices_data
            ])
        return instance


# -----------------------------
# Reading Passage
# -----------------------------
class ReadingPassageSerializer(serializers.ModelSerializer):
    questions_count = serializers.SerializerMethodField()

    class Meta:
        model = ReadingPassage
        fields = ['id', 'book', 'title', 'content', 'questions_count']

    def get_questions_count(self, obj):
        return obj.reading_questions.count()

    def validate_content(self, value):
        if len(value.strip()) < 50:
            raise serializers.ValidationError("يجب أن يكون النص أطول من 50 حرف.")
        return value


# -----------------------------
# Detail Serializers (Optional use)
# -----------------------------
class MCQQuestionDetailSerializer(MCQQuestionSerializer):
    mcq_choices = MCQChoiceSerializer(many=True, read_only=True)

class MatchingQuestionDetailSerializer(MatchingQuestionSerializer):
    matching_pairs = MatchingPairSerializer(many=True, read_only=True)

class ReadingQuestionDetailSerializer(ReadingQuestionSerializer):
    reading_choices = ReadingChoiceSerializer(many=True, read_only=True)

class TrueFalseQuestionDetailSerializer(TrueFalseQuestionSerializer):
    pass
