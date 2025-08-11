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
        fields = ['id', 'text', 'is_correct']


class MCQQuestionSerializer(serializers.ModelSerializer):
    mcq_choices = MCQChoiceSerializer(many=True, source = "choices")

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
        choices_data = validated_data.pop('choices')
        question = MCQQuestion.objects.create(**validated_data)
    
        MCQChoice.objects.bulk_create([
            MCQChoice(question=question, **choice) for choice in choices_data
        ])
    
        # حدد الإجابة الصحيحة
        correct_choice = next((c['text'] for c in choices_data if c.get('is_correct')), None)
        if correct_choice:
            question.correct_answer = correct_choice
            question.save()
    
        return question


    def update(self, instance, validated_data):
        choices_data = validated_data.pop('choices', None) 
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if choices_data is not None:
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
    matching_pairs = MatchingPairSerializer(many=True, source='pairs')
    pairs_count = serializers.SerializerMethodField()  # إضافة عدد الأزواج
    
    class Meta:
        model = MatchingQuestion
        fields = ['id', 'book', 'text', 'matching_pairs', 'pairs_count','difficulty']
        
    def get_pairs_count(self, obj):
        """حساب عدد أزواج المطابقة"""
        return obj.pairs.count()
    
    def validate_text(self, value):
        """التحقق من نص السؤال"""
        if not value or not value.strip():
            raise serializers.ValidationError("نص السؤال مطلوب")
        return value.strip()
    
    def validate_matching_pairs(self, value):
        """التحقق من أزواج المطابقة"""
        if not value:
            raise serializers.ValidationError("يجب إضافة أزواج للمطابقة")
        
        if len(value) < 2:
            raise serializers.ValidationError("يجب أن يحتوي السؤال على زوجين على الأقل")
        
        # التحقق من عدم تكرار المفاتيح
        keys = [pair['match_key'].strip() for pair in value]
        if len(keys) != len(set(keys)):
            raise serializers.ValidationError("لا يمكن تكرار مفاتيح المطابقة")
        
        # التحقق من عدم تكرار العناصر اليسرى
        left_items = [pair['left_item'].strip().lower() for pair in value]
        if len(left_items) != len(set(left_items)):
            raise serializers.ValidationError("لا يمكن تكرار العناصر اليسرى")
        
        # التحقق من عدم تكرار العناصر اليمنى
        right_items = [pair['right_item'].strip().lower() for pair in value]
        if len(right_items) != len(set(right_items)):
            raise serializers.ValidationError("لا يمكن تكرار العناصر اليمنى")
        
        return value
    
    def create(self, validated_data):
        """إنشاء سؤال مطابقة جديد"""
        pairs_data = validated_data.pop('pairs')
        question = MatchingQuestion.objects.create(**validated_data)
        
        # إنشاء الأزواج
        pairs_to_create = [
            MatchingPair(question=question, **pair_data) 
            for pair_data in pairs_data
        ]
        MatchingPair.objects.bulk_create(pairs_to_create)
        
        return question
    
    def update(self, instance, validated_data):
        """تعديل سؤال مطابقة موجود"""
        pairs_data = validated_data.pop('pairs', None)
        
        # تعديل بيانات السؤال الأساسية
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # تعديل الأزواج إذا تم تمريرها
        if pairs_data is not None:
            # حذف الأزواج القديمة
            instance.pairs.all().delete()
            
            # إنشاء الأزواج الجديدة
            pairs_to_create = [
                MatchingPair(question=instance, **pair_data) 
                for pair_data in pairs_data
            ]
            MatchingPair.objects.bulk_create(pairs_to_create)
        
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
    reading_choices = ReadingChoiceSerializer(many=True, required=False, source='choices')

    class Meta:
        model = ReadingQuestion
        fields = ['id', 'passage', 'text', 'correct_answer', 'reading_choices', 'book','difficulty']
        read_only_fields = ['passage']

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
    reading_questions = ReadingQuestionSerializer(many=True, required=False)

    class Meta:
        model = ReadingPassage
        fields = ['id', 'book', 'title', 'content', 'questions_count', 'reading_questions']

    def get_questions_count(self, obj):
        return obj.reading_questions.count()

    def validate_content(self, value):
        if len(value.strip()) < 50:
            raise serializers.ValidationError("يجب أن يكون النص أطول من 50 حرف.")
        return value

    def create(self, validated_data):
        questions_data = validated_data.pop('reading_questions', [])
        passage = ReadingPassage.objects.create(**validated_data)

        for q_data in questions_data:
            choices_data = q_data.pop('reading_choices', [])
            question = ReadingQuestion.objects.create(passage=passage, **q_data)

            if choices_data:
                ReadingChoice.objects.bulk_create([
                    ReadingChoice(question=question, **choice) for choice in choices_data
                ])

        return passage



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


