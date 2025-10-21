from django.db import models
import json
import uuid

# -------------------------------------------------------------------
class Book(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    price_sar = models.DecimalField(max_digits=8, decimal_places=2, default=0)  # 💰 مهم لو هتربطه بالدفع


    def __str__(self):
        return self.title

# -------------------------------------------------------------------
class QuestionBase(models.Model):
    DIFFICULTY_CHOICES = (
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    )

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="all_questions")
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES)
    question_text = models.TextField()

    class Meta:
        abstract = True

# -------------------------------------------------------------------
class MCQQuestion(QuestionBase):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="mcq_questions")
    text = models.CharField(max_length=250)
    correct_answer = models.CharField(max_length=255, default="question")

    def __str__(self):
        return self.text


class MCQChoice(models.Model):
    question = models.ForeignKey(MCQQuestion, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text

# -------------------------------------------------------------------
class MatchingQuestion(QuestionBase):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="matching_question")
    text = models.CharField(max_length=255, null=True)

    # لو هتدخل الـ pairs كـ JSON مباشر
    json_pairs = models.JSONField(help_text="List of pairs to match", null=True, blank=True)

    def __str__(self):
        return self.text

class MatchingPair(models.Model):
    question = models.ForeignKey(MatchingQuestion, on_delete=models.CASCADE, related_name="pairs")
    left_item = models.CharField(max_length=255)
    right_item = models.CharField(max_length=255)
    match_key = models.CharField(max_length=50)

# -------------------------------------------------------------------
class TrueFalseQuestion(QuestionBase):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="true_question")
    is_true = models.BooleanField()
    text = models.CharField(max_length=255, null=True)

    def __str__(self):
        return self.question_text

# -------------------------------------------------------------------


class ReadingComprehension(QuestionBase):
    # معلومات القطعة الأساسية
    book = models.ForeignKey('Book', on_delete=models.CASCADE, related_name="reading_comprehensions")
    title = models.CharField(max_length=255, verbose_name="عنوان القطعة")
    content = models.TextField(verbose_name="محتوى القطعة")
    
    # الأسئلة والإجابات في شكل JSON
    questions_data = models.JSONField(
        default=list,
        verbose_name="الأسئلة والإجابات",
        help_text="قائمة بالأسئلة والاختيارات والإجابات الصحيحة"
    )
    
    def __str__(self):
        return f"{self.title} - {self.book.title if self.book else 'بدون كتاب'}"
    
    # دوال مساعدة للتعامل مع الأسئلة
    def add_question(self, question_text, choices, correct_answer):
        """إضافة سؤال جديد"""
        question_data = {
            'question': question_text,
            'choices': choices,  # قائمة بالاختيارات
            'correct_answer': correct_answer  # الإجابة الصحيحة
        }
        
        if not self.questions_data:
            self.questions_data = []
        
        self.questions_data.append(question_data)
        self.save()




