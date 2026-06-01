from django.contrib import admin

from .models import Specialty, UniversityInfo, UniversityAbout, UniversityContacts, UniversityDates, UniversityWebsite

from .models import ValidCredential

@admin.register(ValidCredential)
class ValidCredentialAdmin(admin.ModelAdmin):
    list_display = ('university_code', 'credential_number', 'is_used')
    list_filter = ('university_code', 'is_used')
    search_fields = ('credential_number',)

@admin.register(UniversityInfo)
class UniversityInfoAdmin(admin.ModelAdmin):
    list_display = ('abbr', 'full_name', 'slug')

from .models import UniversityAbout

@admin.register(UniversityAbout)
class UniversityAboutAdmin(admin.ModelAdmin):
    list_display = ('university',)


@admin.register(UniversityContacts)
class UniversityContactsAdmin(admin.ModelAdmin):
    list_display = ('university',)

@admin.register(UniversityDates)
class UniversityDatesAdmin(admin.ModelAdmin):
    list_display = ('university',)

@admin.register(UniversityWebsite)
class UniversityWebsiteAdmin(admin.ModelAdmin):
    list_display = ('university',)

@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ('university', 'code', 'name', 'min_score', 'high_score')
    list_filter = ('university',)
    search_fields = ('name', 'code')
    ordering = ('university', 'code')