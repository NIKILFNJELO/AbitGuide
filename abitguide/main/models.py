from django.contrib.auth.models import User
from django.db import models
import json


class Profile(models.Model):
    ROLE_CHOICES = [
        ('applicant', 'Абітурієнт'),
        ('parent', 'Батьки'),
        ('university_rep', 'Представник ЗВО'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)

    full_name = models.CharField(max_length=255, unique=True, null=True, blank=True)
    id_number = models.CharField(max_length=12, blank=True, null=True)
    id_prefix = models.CharField(max_length=10, blank=True, null=True)
    university_slug = models.CharField(max_length=50, blank=True, null=True)  


    is_registered = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username
    
class ValidCredential(models.Model):
    university_code = models.CharField(max_length=20)   # ХНЕУ, ХНУРЕ 
    credential_number = models.CharField(max_length=20) # 123456789012
    is_used = models.BooleanField(default=False)

    created_by = models.ForeignKey(
    User,
    on_delete=models.SET_NULL,
    null=True, blank=True,
    related_name='created_credentials'
            )
    used_by = models.ForeignKey(
    User,
    on_delete=models.SET_NULL,
    null=True, blank=True,
    related_name='used_credential'
            )

    class Meta:
        unique_together = ('university_code', 'credential_number')

    def __str__(self):
        return f"{self.university_code}-{self.credential_number} ({'використано' if self.is_used else 'вільне'})"


class SavedRecommendation(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recommendations')
    created_at = models.DateTimeField(auto_now_add=True)
    university = models.CharField(max_length=200)
    avg_score  = models.FloatField()
    fitting_specs = models.TextField()  # JSON список підходящих спеціальностей

    def get_fitting_specs(self):
        return json.loads(self.fitting_specs)

    def set_fitting_specs(self, specs_list):
        self.fitting_specs = json.dumps(specs_list, ensure_ascii=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} — {self.university} — {self.avg_score} ({self.created_at:%d.%m.%Y})"

class UniversityInfo(models.Model):
    slug = models.CharField(max_length=50, unique=True)  
    abbr = models.CharField(max_length=20)               
    full_name = models.CharField(max_length=300)       
    photo_url = models.URLField(blank=True, null=True)  
    has_programs = models.BooleanField(default=False)  # ← додай це


    def __str__(self):
        return self.abbr
    
class UniversityAbout(models.Model):
    university = models.OneToOneField(UniversityInfo, on_delete=models.CASCADE, related_name='about')
    title = models.CharField(max_length=300)
    paragraph_1 = models.TextField(blank=True)
    paragraph_2 = models.TextField(blank=True)
    paragraph_3 = models.TextField(blank=True)
    paragraph_4 = models.TextField(blank=True)
    paragraph_5 = models.TextField(blank=True)

    def __str__(self):
        return f"Про {self.university.abbr}"
    
class UniversityContacts(models.Model):
    university   = models.OneToOneField(UniversityInfo, on_delete=models.CASCADE, related_name='contacts')
    address      = models.CharField(max_length=300, blank=True)
    phone_1      = models.CharField(max_length=50, blank=True)
    phone_2      = models.CharField(max_length=50, blank=True)
    email_pk     = models.EmailField(blank=True)
    email_uni    = models.EmailField(blank=True)
    youtube      = models.CharField(max_length=200, blank=True)
    telegram     = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"Контакти {self.university.abbr}"


def _safe_json(value):
    try:
        result = json.loads(value or '[]')
        if isinstance(result, str):       # подвійне кодування
            result = json.loads(result)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []

class UniversityDates(models.Model):
    university = models.OneToOneField(UniversityInfo, on_delete=models.CASCADE, related_name='dates')
    july       = models.TextField(blank=True, default='[]')
    august     = models.TextField(blank=True, default='[]')
    sep_oct    = models.TextField(blank=True, default='[]')

    def get_july(self):    return _safe_json(self.july)
    def get_august(self):  return _safe_json(self.august)
    def get_sep_oct(self): return _safe_json(self.sep_oct)
      

class UniversityWebsite(models.Model):
    university = models.OneToOneField(UniversityInfo, on_delete=models.CASCADE, related_name='website')
    site_url   = models.URLField(blank=True)
    image_url  = models.URLField(blank=True)

    def __str__(self):
        return f"Сайт {self.university.abbr}"
    

class Specialty(models.Model):
    university = models.ForeignKey(
        UniversityInfo, 
        on_delete=models.CASCADE, 
        related_name='specialties'
    )
    name = models.CharField(max_length=300)
    code = models.CharField(max_length=20, blank=True, null=True)
    about = models.TextField(blank=True, null=True)
    what_to_study = models.TextField(blank=True, null=True)
    career = models.TextField(blank=True, null=True)
    min_score = models.FloatField(blank=True, null=True)
    high_score = models.FloatField(blank=True, null=True)

    class Meta:
        unique_together = ('university', 'name')

    def __str__(self):
        return f"{self.university.abbr} — {self.name}"
    
class EducationalProgram(models.Model):
    university = models.ForeignKey(UniversityInfo, on_delete=models.CASCADE, related_name='educational_programs')
    specialty = models.ForeignKey(Specialty, on_delete=models.CASCADE, related_name='educational_programs')
    name = models.CharField('Назва освітньої програми', max_length=200)
    
    def __str__(self):
        return f'{self.specialty.code} - {self.name}'


class AdminAction(models.Model):
    ACTION_CHOICES = [
        ('block', 'Блокування'),
        ('unblock', 'Розблокування'),
        ('delete', 'Видалення'),
    ]

    admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='admin_actions'
    )
    target_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='received_actions'
    )
    action_type = models.CharField(max_length=30, choices=ACTION_CHOICES)
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_active_block(self):
        last = AdminAction.objects.filter(
            target_user=self.target_user
        ).order_by('-created_at').first()
        return last.action_type == 'block' if last else False

    def __str__(self):
        return f"{self.admin} → {self.target_user}: {self.action_type}"