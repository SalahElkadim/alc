from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, UserBook,UserSession

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'full_name', 'user_type', 'is_staff')
    list_filter = ('is_staff', 'user_type')
    ordering = ('email',)  # بدل username
    search_fields = ('email', 'full_name', 'phone')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'phone', 'user_type')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'phone', 'user_type', 'password1', 'password2', 'is_staff', 'is_active')}
        ),
    )

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(UserBook)
admin.site.register(UserSession)



