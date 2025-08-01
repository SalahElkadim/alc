from django.db import models

# -------------------------------------------------------------------
class Book(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

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
class ReadingPassage(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="reading_passages")
    title = models.CharField(max_length=255)
    content = models.TextField()

    def __str__(self):
        return self.title

class ReadingQuestion(QuestionBase):
    passage = models.ForeignKey(ReadingPassage, on_delete=models.CASCADE, related_name="reading_questions")
    correct_answer = models.CharField(max_length=255)
    text = models.CharField(max_length=255, null=True)


    def __str__(self):
        return self.text
    
class ReadingChoice(models.Model):
    question = models.ForeignKey(ReadingQuestion, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)  # إضافة هذا الحقل

    def __str__(self):
        return self.text
