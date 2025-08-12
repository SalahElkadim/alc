from django.db import models


class Exam(models.Model):
    student = models.ForeignKey("auth.User", on_delete=models.CASCADE, related_name="exams")
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=30)
    is_finished = models.BooleanField(default=False)
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    def __str__(self):
        return f"Exam for {self.student} - {self.book.title}"


class ExamQuestion(models.Model):
    QUESTION_TYPES = [
        ('mcq', 'MCQ'),
        ('matching', 'Matching'),
        ('truefalse', 'True/False'),
        ('reading', 'Reading Comprehension'),
    ]

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
