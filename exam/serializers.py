from rest_framework import serializers
from django.utils import timezone
from .models import Exam, ExamQuestion
from questions.models import Book, MCQQuestion, TrueFalseQuestion, MatchingQuestion, ReadingComprehension
from users.models import CustomUser


class ExamQuestionSerializer(serializers.ModelSerializer):
    """Serializer لعرض أسئلة الامتحان للطلاب"""
    choices = serializers.SerializerMethodField()
    pairs = serializers.SerializerMethodField()
    reading_content = serializers.SerializerMethodField()
    reading_title = serializers.SerializerMethodField()
    
    class Meta:
        model = ExamQuestion
        fields = [
            'id', 'question_type', 'question_text', 'choices', 
            'pairs', 'reading_content', 'reading_title', 'points'
        ]
    
    def get_choices(self, obj):
        """إرجاع الاختيارات للـ MCQ و True/False"""
        if obj.question_type == 'mcq':
            if obj.correct_answer and 'choices' in obj.correct_answer:
                return [choice['text'] for choice in obj.correct_answer['choices']]
            # Fallback للنظام القديم
            try:
                mcq = MCQQuestion.objects.prefetch_related('choices').get(id=obj.question_id)
                return [c.text for c in mcq.choices.all()]
            except MCQQuestion.DoesNotExist:
                return []
        elif obj.question_type == 'truefalse':
            return ["True", "False"]
        elif obj.question_type == 'reading':
            if obj.correct_answer and 'choices' in obj.correct_answer:
                return obj.correct_answer['choices']
        return []
    
    def get_pairs(self, obj):
        """إرجاع الأزواج للـ Matching"""
        if obj.question_type == 'matching':
            if obj.correct_answer and 'pairs' in obj.correct_answer:
                return obj.correct_answer['pairs']
            # Fallback
            try:
                matching = MatchingQuestion.objects.prefetch_related('pairs').get(id=obj.question_id)
                return [{"left": p.left_item, "right": p.right_item} for p in matching.pairs.all()]
            except MatchingQuestion.DoesNotExist:
                return []
        return []
    
    def get_reading_content(self, obj):
        """إرجاع محتوى القراءة"""
        if obj.question_type == 'reading' and obj.correct_answer:
            return obj.correct_answer.get('reading_content', '')
        return None
    
    def get_reading_title(self, obj):
        """إرجاع عنوان القراءة"""
        if obj.question_type == 'reading' and obj.correct_answer:
            return obj.correct_answer.get('reading_title', 'Reading Passage')
        return None


class ExamQuestionResultSerializer(serializers.ModelSerializer):
    """Serializer لعرض نتائج الأسئلة بعد التصحيح"""
    correct_answer_display = serializers.SerializerMethodField()
    student_answer_display = serializers.SerializerMethodField()
    
    class Meta:
        model = ExamQuestion
        fields = [
            'id', 'question_type', 'question_text', 'student_answer', 
            'student_answer_display', 'correct_answer', 'correct_answer_display',
            'is_correct', 'points'
        ]
    
    def get_correct_answer_display(self, obj):
        """عرض الإجابة الصحيحة بشكل قابل للقراءة"""
        if obj.question_type == 'mcq':
            if isinstance(obj.correct_answer, dict) and 'answer_text' in obj.correct_answer:
                return obj.correct_answer['answer_text']
        elif obj.question_type == 'truefalse':
            if isinstance(obj.correct_answer, dict) and 'answer' in obj.correct_answer:
                return "True" if obj.correct_answer['answer'] else "False"
        elif obj.question_type == 'reading':
            if isinstance(obj.correct_answer, dict) and 'answer' in obj.correct_answer:
                return obj.correct_answer['answer']
        elif obj.question_type == 'matching':
            if isinstance(obj.correct_answer, dict) and 'matches' in obj.correct_answer:
                return obj.correct_answer['matches']
        return obj.correct_answer
    
    def get_student_answer_display(self, obj):
        """عرض إجابة الطالب بشكل قابل للقراءة"""
        if obj.student_answer is None:
            return "No Answer"
        
        if obj.question_type == 'mcq':
            # البحث عن النص المقابل للـ ID
            if isinstance(obj.correct_answer, dict) and 'choices' in obj.correct_answer:
                for choice in obj.correct_answer['choices']:
                    if str(choice['id']) == str(obj.student_answer):
                        return choice['text']
        elif obj.question_type == 'truefalse':
            if isinstance(obj.student_answer, bool):
                return "True" if obj.student_answer else "False"
            elif isinstance(obj.student_answer, str):
                return obj.student_answer.capitalize()
        
        return obj.student_answer


class ExamSerializer(serializers.ModelSerializer):
    """Serializer أساسي للامتحان"""
    book_title = serializers.CharField(source='book.title', read_only=True)
    student_name = serializers.SerializerMethodField(read_only=True)
    time_remaining = serializers.SerializerMethodField(read_only=True)
    time_taken_minutes = serializers.SerializerMethodField(read_only=True)
    questions_count = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Exam
        fields = [
            'id', 'book_title', 'student_name', 'start_time', 'end_time',
            'duration_minutes', 'is_finished', 'score', 'time_remaining',
            'time_taken_minutes', 'questions_count'
        ]
    
    def get_student_name(self, obj):
        return obj.student.get_full_name() or obj.student.username
    
    def get_time_remaining(self, obj):
        """حساب الوقت المتبقي بالدقائق"""
        if obj.is_finished:
            return 0
        
        time_elapsed = (timezone.now() - obj.start_time).total_seconds() / 60
        time_remaining = max(0, obj.duration_minutes - time_elapsed)
        return int(time_remaining)
    
    def get_time_taken_minutes(self, obj):
        """حساب الوقت المستغرق"""
        if obj.start_time and obj.end_time:
            return int((obj.end_time - obj.start_time).total_seconds() / 60)
        elif obj.start_time and not obj.is_finished:
            return int((timezone.now() - obj.start_time).total_seconds() / 60)
        return None
    
    def get_questions_count(self, obj):
        return obj.exam_questions.count()


class ExamDetailSerializer(ExamSerializer):
    """Serializer مفصل للامتحان مع الأسئلة"""
    questions = serializers.SerializerMethodField()
    
    class Meta(ExamSerializer.Meta):
        fields = ExamSerializer.Meta.fields + ['questions']
    
    def get_questions(self, obj):
        """تجميع الأسئلة مع معالجة خاصة للقراءة"""
        questions = []
        reading_map = {}
        
        exam_questions = obj.exam_questions.select_related().all()
        
        for eq in exam_questions:
            if eq.question_type == "reading":
                # تجميع أسئلة القراءة
                reading_key = f"reading_{eq.question_id}"
                
                if reading_key not in reading_map:
                    reading_map[reading_key] = {
                        "id": reading_key,
                        "type": "reading",
                        "title": eq.correct_answer.get('reading_title', 'Reading Passage'),
                        "content": eq.correct_answer.get('reading_content', ''),
                        "sub_questions": []
                    }
                
                reading_map[reading_key]["sub_questions"].append({
                    "id": eq.id,
                    "text": eq.question_text,
                    "choices": eq.correct_answer.get('choices', [])
                })
            else:
                # الأسئلة العادية
                serializer = ExamQuestionSerializer(eq)
                question_data = serializer.data
                questions.append(question_data)
        
        # إضافة أسئلة القراءة المجمعة
        questions.extend(list(reading_map.values()))
        
        return questions


class ExamResultSerializer(ExamSerializer):
    """Serializer لنتائج الامتحان مع الإحصائيات"""
    statistics = serializers.SerializerMethodField()
    results = serializers.SerializerMethodField()
    
    class Meta(ExamSerializer.Meta):
        fields = ExamSerializer.Meta.fields + ['statistics', 'results']
    
    def get_statistics(self, obj):
        """حساب الإحصائيات"""
        exam_questions = obj.exam_questions.all()
        
        stats = {
            "total_questions": exam_questions.count(),
            "correct_answers": exam_questions.filter(is_correct=True).count(),
            "by_type": {}
        }
        
        # إحصائيات حسب النوع
        for eq in exam_questions:
            if eq.question_type not in stats["by_type"]:
                stats["by_type"][eq.question_type] = {"total": 0, "correct": 0}
            
            stats["by_type"][eq.question_type]["total"] += 1
            if eq.is_correct:
                stats["by_type"][eq.question_type]["correct"] += 1
        
        # حساب النسب المئوية
        for q_type in stats["by_type"]:
            total = stats["by_type"][q_type]["total"]
            correct = stats["by_type"][q_type]["correct"]
            stats["by_type"][q_type]["percentage"] = round((correct / total) * 100, 2) if total > 0 else 0
        
        return stats
    
    def get_results(self, obj):
        """تجميع النتائج حسب النوع"""
        results = {
            "mcq": [],
            "truefalse": [],
            "matching": [],
            "reading": []
        }
        
        exam_questions = obj.exam_questions.all()
        
        for eq in exam_questions:
            serializer = ExamQuestionResultSerializer(eq)
            results[eq.question_type].append(serializer.data)
        
        return results


# Serializers للطلبات (Requests)
class GenerateExamRequestSerializer(serializers.Serializer):
    """Serializer لطلب إنشاء امتحان"""
    book_id = serializers.IntegerField(required=True)
    duration = serializers.IntegerField(default=30, min_value=5, max_value=180)
    
    def validate_book_id(self, value):
        """التحقق من وجود الكتاب"""
        try:
            Book.objects.get(id=value)
        except Book.DoesNotExist:
            raise serializers.ValidationError("Book not found")
        return value
    
    def validate_duration(self, value):
        """التحقق من مدة الامتحان"""
        if not (5 <= value <= 180):
            raise serializers.ValidationError("Duration must be between 5 and 180 minutes")
        return value


class SubmitAnswerSerializer(serializers.Serializer):
    """Serializer لإجابة واحدة"""
    question_id = serializers.IntegerField(required=True)
    answer = serializers.JSONField(required=True)  # يمكن أن تكون string, int, dict, etc.


class SubmitExamRequestSerializer(serializers.Serializer):
    """Serializer لتسليم الامتحان"""
    answers = SubmitAnswerSerializer(many=True, required=True)
    
    def validate_answers(self, value):
        """التحقق من وجود إجابات"""
        if not value:
            raise serializers.ValidationError("No answers provided")
        return value


# Response Serializers
class GenerateExamResponseSerializer(serializers.Serializer):
    """Serializer لرد إنشاء الامتحان"""
    exam_id = serializers.IntegerField()
    questions_count = serializers.IntegerField()
    duration_minutes = serializers.IntegerField()
    message = serializers.CharField()


class SubmitExamResponseSerializer(serializers.Serializer):
    """Serializer لرد تسليم الامتحان"""
    exam_id = serializers.IntegerField()
    score = serializers.DecimalField(max_digits=5, decimal_places=2)
    total_points = serializers.DecimalField(max_digits=5, decimal_places=2)
    earned_points = serializers.DecimalField(max_digits=5, decimal_places=2)
    correct_answers = serializers.IntegerField()
    total_questions = serializers.IntegerField()
    message = serializers.CharField()


class StudentExamsListSerializer(serializers.Serializer):
    """Serializer لقائمة امتحانات الطالب"""
    exams = ExamSerializer(many=True)
    total_exams = serializers.IntegerField()


# Nested Serializers للاستعلامات المعقدة
class BookBasicSerializer(serializers.ModelSerializer):
    """Serializer مبسط للكتاب"""
    class Meta:
        model = Book
        fields = ['id', 'title']


class StudentBasicSerializer(serializers.ModelSerializer):
    """Serializer مبسط للطالب"""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'full_name', 'email']
    
    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


# Serializer للـ Admin/Teacher Views (إضافي)
class ExamAdminSerializer(ExamSerializer):
    """Serializer للمدرسين/الإدارة لرؤية تفاصيل أكثر"""
    student = StudentBasicSerializer(read_only=True)
    book = BookBasicSerializer(read_only=True)
    
    class Meta:
        model = Exam
        fields = [
            'id', 'student', 'book', 'start_time', 'end_time',
            'duration_minutes', 'is_finished', 'score',
            'time_taken_minutes', 'questions_count'
        ]