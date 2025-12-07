from rest_framework import serializers
from .models import (
    MCQQuestion, MCQChoice,
    MatchingQuestion, MatchingPair,
    TrueFalseQuestion,Book,ReadingComprehension
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
        fields = ['id', 'text', 'is_correct']


class MCQQuestionSerializer(serializers.ModelSerializer):
    mcq_choices = MCQChoiceSerializer(many=True)

    class Meta:
        model = MCQQuestion
        fields = ['id', 'book', 'text', 'difficulty', 'correct_answer', 'mcq_choices']

    def validate_mcq_choices(self, value):
        if len(value) < 2:
            raise serializers.ValidationError("يجب أن يحتوي السؤال على خيارين على الأقل.")

        texts = [choice['text'].strip() for choice in value]
        if len(texts) != len(set(texts)):
            raise serializers.ValidationError("يجب ألا تتكرر نصوص الخيارات.")
        return value

    def create(self, validated_data):
        choices_data = validated_data.pop('mcq_choices')
        question = MCQQuestion.objects.create(**validated_data)

        MCQChoice.objects.bulk_create([
            MCQChoice(question=question, **choice) for choice in choices_data
        ])

        # تعيين الإجابة الصحيحة
        correct_choice = next((c['text'] for c in choices_data if c.get('is_correct')), None)
        if correct_choice:
            question.correct_answer = correct_choice
            question.save()

        return question


    def update(self, instance, validated_data):
        choices_data = validated_data.pop('mcq_choices', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if choices_data:
            instance.choices.all().delete()
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
        
    def validate_match_key(self, value):
        """التحقق من صحة مفتاح المطابقة"""
        if not value or not value.strip():
            raise serializers.ValidationError("مفتاح المطابقة مطلوب")
        return value.strip()
    
    def validate_left_item(self, value):
        """التحقق من العنصر الأيسر"""
        if not value or not value.strip():
            raise serializers.ValidationError("العنصر الأيسر مطلوب")
        return value.strip()
    
    def validate_right_item(self, value):
        """التحقق من العنصر الأيمن"""
        if not value or not value.strip():
            raise serializers.ValidationError("العنصر الأيمن مطلوب")
        return value.strip()

class MatchingQuestionSerializer(serializers.ModelSerializer):
    # للقراءة
    matching_pairs = serializers.SerializerMethodField()
    # للكتابة
    input_matching_pairs = MatchingPairSerializer(many=True, source='pairs', write_only=True)
    
    pairs_count = serializers.SerializerMethodField()

    class Meta:
        model = MatchingQuestion
        fields = [
            'id', 'book', 'text',
            'matching_pairs', 'input_matching_pairs',
            'pairs_count', 'difficulty'
        ]

    def get_matching_pairs(self, obj):
        left_items = [p.left_item for p in obj.pairs.all()]
        right_items = [p.right_item for p in obj.pairs.all()]
        return [
            {"left_item": left_items},
            {"right_item": right_items}
        ]

    def get_pairs_count(self, obj):
        return obj.pairs.count()

    def create(self, validated_data):
        pairs_data = validated_data.pop('pairs')
        question = MatchingQuestion.objects.create(**validated_data)
        pairs_to_create = [MatchingPair(question=question, **pair_data) for pair_data in pairs_data]
        MatchingPair.objects.bulk_create(pairs_to_create)
        return question

    def update(self, instance, validated_data):
        pairs_data = validated_data.pop('pairs', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if pairs_data is not None:
            instance.pairs.all().delete()
            pairs_to_create = [MatchingPair(question=instance, **pair_data) for pair_data in pairs_data]
            MatchingPair.objects.bulk_create(pairs_to_create)

        return instance



# -----------------------------
# True/False Question
# -----------------------------
class TrueFalseQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrueFalseQuestion
        fields = ['id', 'book', 'text', 'is_true','difficulty']




class ReadingComprehensionSerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source='book.title', read_only=True)
    
    class Meta:
        model = ReadingComprehension
        fields = ['id', 'book', 'book_title', 'title', 'content', 'questions_data' ,'difficulty'
                ]
    
    def validate_questions_data(self, value):
        """التحقق من صحة بيانات الأسئلة"""
        if not isinstance(value, list):
            raise serializers.ValidationError("الأسئلة يجب أن تكون في شكل قائمة")
        
        for i, question in enumerate(value):
            if not isinstance(question, dict):
                raise serializers.ValidationError(f"السؤال رقم {i+1} يجب أن يكون object")
            
            required_fields = ['question', 'choices', 'correct_answer']
            for field in required_fields:
                if field not in question:
                    raise serializers.ValidationError(f"السؤال رقم {i+1} يفتقد للحقل: {field}")
            
            # التحقق من الاختيارات
            choices = question.get('choices')
            if not isinstance(choices, list) or len(choices) < 2:
                raise serializers.ValidationError(f"السؤال رقم {i+1}: الاختيارات يجب أن تكون قائمة تحتوي على خيارين على الأقل")
            
            # التحقق من الإجابة الصحيحة
            correct_answer = question.get('correct_answer')
            if correct_answer not in choices:
                raise serializers.ValidationError(f"السؤال رقم {i+1}: الإجابة الصحيحة يجب أن تكون من ضمن الاختيارات")
        
        return value


