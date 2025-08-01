from django.contrib import admin
from .models import (
    Book,
    MCQQuestion, MCQChoice,
    MatchingQuestion, MatchingPair,
    TrueFalseQuestion,
    ReadingPassage, ReadingQuestion, ReadingChoice
)

# -------------------------
@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'created_at']
    search_fields = ['title']


# -------------------------
class MCQChoiceInline(admin.TabularInline):
    model = MCQChoice
    extra = 1

@admin.register(MCQQuestion)
class MCQQuestionAdmin(admin.ModelAdmin):
    list_display = ['id', 'question_text', 'difficulty', 'book', 'correct_answer']
    list_filter = ['difficulty', 'book']
    search_fields = ['question_text']
    inlines = [MCQChoiceInline]


# -------------------------
class MatchingPairInline(admin.TabularInline):
    model = MatchingPair
    extra = 1

@admin.register(MatchingQuestion)
class MatchingQuestionAdmin(admin.ModelAdmin):
    list_display = ['id', 'question_text', 'difficulty', 'book']
    list_filter = ['difficulty', 'book']
    search_fields = ['question_text']
    inlines = [MatchingPairInline]


# -------------------------
@admin.register(TrueFalseQuestion)
class TrueFalseQuestionAdmin(admin.ModelAdmin):
    list_display = ['id', 'question_text', 'difficulty', 'book', 'is_true']
    list_filter = ['difficulty', 'book']
    search_fields = ['question_text']


# -------------------------
@admin.register(ReadingPassage)
class ReadingPassageAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'book']
    search_fields = ['title']


class ReadingChoiceInline(admin.TabularInline):
    model = ReadingChoice
    extra = 1

@admin.register(ReadingQuestion)
class ReadingQuestionAdmin(admin.ModelAdmin):
    list_display = ['id', 'question_text', 'difficulty', 'passage', 'correct_answer']
    list_filter = ['difficulty', 'passage']
    search_fields = ['question_text']
    inlines = [ReadingChoiceInline]
