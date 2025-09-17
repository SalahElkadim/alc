from django.db import models
from questions.models import Book
from users.models import CustomUser
import uuid

class Exam(models.Model):
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="exams")
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=30)
    is_finished = models.BooleanField(default=False)
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    difficulty = models.CharField(max_length=30, choices=[("easy", "Easy"), ("medium", "Medium"), ("hard", "Hard")], null= True)


    def __str__(self):
        return f"Exam for {self.student} - {self.book.title}"


class ExamQuestion(models.Model):
    QUESTION_TYPES = [
        ('mcq', 'MCQ'),
        ('matching', 'Matching'),
        ('truefalse', 'True/False'),
        ('reading', 'Reading Comprehension'),
    ]
    public_id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)  # <-- الجديد
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="exam_questions")
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    question_id = models.PositiveIntegerField()  # ID في الجدول الأصلي (MCQ, Matching, إلخ)
    question_text = models.TextField()  # نسخة محفوظة من السؤال
    correct_answer = models.JSONField()  # عشان نحفظ الإجابة وقت إنشاء الامتحان
    student_answer = models.JSONField(null=True, blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    points = models.DecimalField(max_digits=5, decimal_places=2, default=1)

    def check_answer(self):
        self.is_correct = (self.student_answer == self.correct_answer)
        return self.is_correct

# model , exam , date , 
class ExamResult(models.Model):
    exam = models.OneToOneField(Exam, on_delete=models.CASCADE, related_name="result")
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="exam_results")
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    score = models.DecimalField(max_digits=5, decimal_places=2)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    letter_grade = models.CharField(max_length=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Result for {self.student} - {self.book.title} ({self.score})"
