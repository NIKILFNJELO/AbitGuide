from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import login as auth_login
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordResetView
from django.contrib.auth.views import PasswordResetConfirmView
from django.shortcuts import render
from datetime import datetime
from .models import SavedRecommendation, Specialty, UniversityAbout, UniversityContacts
import json
from .models import UniversityInfo
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from .models import ValidCredential, AdminAction, Profile
import re


# Головна сторінка
def home(request):
    profile = None
    if request.user.is_authenticated:
        if request.user.is_superuser:
            # Для адміна — окремий контекст без Profile
            return render(request, 'main/home.html', {
                'profile': None,
                'is_admin': True,
            })
        profile = Profile.objects.filter(user=request.user).first()
    return render(request, 'main/home.html', {'profile': profile, 'is_admin': False})


# Декоратор для перевірки авторизації з повідомленням
def login_required_with_message(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Авторизуйтесь!")
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper


# Перевірка чи користувач є адміном для доступу до певних сторінок
def is_admin(user):
    return user.is_authenticated and user.is_superuser


def registration(request):
    errors = {}
    data = request.POST

    if request.method == "POST":
        full_name = data.get("full_name", "").strip()
        email = data.get("email", "").strip()
        password = data.get("password", "")
        role = data.get("role", "")
        id_number = data.get("id_number", "").strip()
        id_prefix = data.get("id_prefix", "").strip().upper()

        # ПІБ
        if not full_name:
            errors["full_name"] = "ПІБ обов'язкове поле"
        else:
            parts = full_name.split()
            if len(parts) != 3:
                errors["full_name"] = "ПІБ повинно складатися з 3 слів"
            else:
                if len(set([p.lower() for p in parts])) == 1:
                    errors["full_name"] = "ПІБ не може складатися з однакових слів"
                elif not all(re.fullmatch(r"[А-ЯІЇЄҐа-яіїєґA-Za-z\-']+", p) for p in parts):
                    errors["full_name"] = "ПІБ може містити лише літери"

        if not errors.get("full_name") and full_name and Profile.objects.filter(full_name=full_name).exists():
            errors["full_name"] = "Такий ПІБ вже існує"

        # EMAIL
        if not email:
            errors["email"] = "Email обов'язковий"
        elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errors["email"] = "Email-адреса повинна містити символ @ та домен"
        elif User.objects.filter(email=email).exists():
            errors["email"] = "Такий email вже використовується"

        # ПАРОЛЬ
        password_errors = []
        if not password:
            password_errors.append("Пароль обов'язковий")
        else:
            if len(password) < 8:
                password_errors.append("мінімум 8 символів")
            if not re.search(r"[a-z]", password):
                password_errors.append("малі латинські літери")
            if not re.search(r"[A-Z]", password):
                password_errors.append("великі латинські літери")
            if not re.search(r"\d", password):
                password_errors.append("цифри")
            if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?`~]", password):
                password_errors.append("спецсимвол (!@#$%^&* тощо)")
        if password_errors:
            errors["password"] = "" + ", ".join(password_errors)

        # РОЛЬ
        role = data.get('role', '').strip()
        if not role or role == 'Оберіть статус':
            errors['role'] = 'Оберіть статус'

        # ПРАЦІВНИК ЗВО
        if role == "university_rep":
            if not id_number:
                errors["id_number"] = "Номер посвідчення обов'язковий"
            elif not re.fullmatch(r"\d{12}", id_number):
                errors["id_number"] = "Потрібно рівно 12 цифр"

            if not id_prefix:
                errors["id_prefix"] = "Абревіатура вузу обов'язкова"
            elif not re.fullmatch(r"[A-ZА-ЯІЇЄ]{2,10}", id_prefix.upper()):
                errors["id_prefix"] = "Введіть абревіатуру вузу (наприклад ХНЕУ)"

            if not errors.get("id_prefix") and not errors.get("id_number"):
                from .models import ValidCredential
                credential = ValidCredential.objects.filter(
                    university_code=id_prefix.upper(),
                    credential_number=id_number,
                    is_used=False
                ).first()
                if not credential:
                    errors["id_number"] = "Посвідчення не знайдено або вже використано"

        if errors:
            return render(request, "main/registration.html", {"errors": errors, "data": data})

        # СТВОРЕННЯ КОРИСТУВАЧА
        user = User.objects.create_user(username=email, email=email, password=password)

        if role == "university_rep":
            from .models import ValidCredential
            cred = ValidCredential.objects.filter(
                university_code=id_prefix.upper(),
                credential_number=id_number
            ).first()
            if cred:
                cred.is_used = True
                cred.save()

        Profile.objects.create(
            user=user,
            role=role,
            full_name=full_name,
            id_number=id_number,
            id_prefix=id_prefix,
            is_registered=True,
            university_slug=UniversityInfo.objects.filter(
                abbr__iexact=id_prefix
            ).values_list('slug', flat=True).first(),
        )
        login(request, user)
        return redirect("home")

    return render(request, "main/registration.html", {"data": {}})


def login_view(request):
    errors = {}
    data = request.POST

    if request.method == "POST":
        username = data.get("username", "").strip()
        password = data.get("password", "")

        if not username:
            errors["username"] = "Введіть логін"
        if not password:
            errors["password"] = "Введіть пароль"

        if username and password:
            # Перевірка чи існує користувач з таким логіном
            try:
                user_obj = User.objects.get(username=username)
                if not user_obj.is_active:
                    errors["password"] = "Ваш обліковий запис було заблоковано. Зверніться до адміністратора."
                else:
                    user = authenticate(request, username=username, password=password)
                    if user is not None:
                        auth_login(request, user)
                        return redirect("home")
                    else:
                        errors["password"] = "Невірний логін або пароль"
            except User.DoesNotExist:
                errors["password"] = "Невірний логін або пароль"

        return render(request, "main/login.html", {"errors": errors, "data": data})

    return render(request, "main/login.html")


def logout_view(request):
    logout(request)
    return redirect('home')


@login_required_with_message
def profile(request):
    if request.user.is_superuser:
        return render(request, 'main/profile.html', {
            'profile': None,
            'role_label': 'Адміністратор',
            'is_admin': True,
            'icon_path': 'main/images/admin.png',
        })

    prof = Profile.objects.filter(user=request.user).first()

    role_display = {
        'applicant':      'Абітурієнт',
        'university_rep': 'Працівник ЗВО',
        'parent':         'Батьки',
    }
    role_icons = {
        'applicant':      'main/images/applicant.png',
        'university_rep': 'main/images/university_rep.png',
        'parent':         'main/images/parent.png',
    }

    return render(request, 'main/profile.html', {
        'profile':    prof,
        'role_label': role_display.get(prof.role, prof.role) if prof else '',
        'is_admin':   False,
        'icon_path':  role_icons.get(prof.role, '') if prof else '',
    })




@login_required_with_message
def universities(request):
    unis_list = UniversityInfo.objects.all().order_by('id')
    profile = Profile.objects.filter(user=request.user).first()
    return render(request, 'main/universities.html', {
        'unis_list': unis_list,
        'uni_count': UniversityInfo.objects.count(),
        'profile': profile,
    })


def university_detail(request, slug):
    uni = get_object_or_404(UniversityInfo, slug=slug)
    return render(request, 'main/university_detail.html', {'uni': uni})


def university_edit_name(request, slug):
    uni = UniversityInfo.objects.get(slug=slug)

    if not request.user.is_authenticated or \
       not hasattr(request.user, 'profile') or \
       request.user.profile.role != 'university_rep' or \
       request.user.profile.university_slug != slug:
        return redirect('universities')

    errors = {}

    if request.method == 'POST':
        abbr = request.POST.get('abbr', '').strip()
        full_name = request.POST.get('full_name', '').strip()

        if not abbr:
            errors['abbr'] = 'Абревіатура не може бути порожньою'
        elif len(abbr) < 2:
            errors['abbr'] = 'Мінімум 2 символи'
        elif len(abbr) > 8:
            errors['abbr'] = 'Максимум 8 символів'

        if not full_name:
            errors['full_name'] = 'Назва не може бути порожньою'
        elif len(full_name) < 20:
            errors['full_name'] = 'Мінімум 20 символів'
        elif len(full_name) > 75:
            errors['full_name'] = 'Максимум 75 символів'

        if not errors:
            uni.abbr = abbr
            uni.full_name = full_name
            uni.save()
            return redirect('universities')

    return render(request, 'main/university_edit_name.html', {'uni': uni, 'errors': errors})

@login_required_with_message
def contacts(request):
    return render(request, 'main/contacts.html')


@login_required_with_message
def sources(request):
    return render(request, 'main/sources.html')

# Кастомна сторінка для скидання пароля з додатковою валідацією
class CustomPasswordResetView(PasswordResetView):
    template_name = 'registration/password_reset_form.html'
    email_template_name = 'registration/password_reset_email.txt'
    subject_template_name = 'registration/password_reset_subject.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_name'] = 'АбітГід'
        return context

    def post(self, request, *args, **kwargs):
        email = request.POST.get('email', '').strip()
        errors = {}
        data = request.POST

        if not email:
            errors['email'] = 'Введіть email'
        elif not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            errors['email'] = 'Email-адреса повинна містити символ @ та домен'

        if errors:
            return render(request, self.template_name, {
                'errors': errors,
                'data': data,
                'site_name': 'АбітГід',
            })

        return super().post(request, *args, **kwargs)

# Кастомна сторінка для підтвердження скидання пароля з додатковою валідацією
class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'registration/password_reset_confirm.html'

    def post(self, request, *args, **kwargs):
        p1 = request.POST.get('new_password1', '').strip()
        p2 = request.POST.get('new_password2', '').strip()
        errors = {}

        if not p1:
            errors['new_password1'] = 'Введіть новий пароль'
        elif len(p1) < 8:
            errors['new_password1'] = 'Пароль має містити щонайменше 8 символів'

        if not p2:
            errors['new_password2'] = 'Підтвердіть пароль'
        elif p1 and p2 and p1 != p2:
            errors['new_password2'] = 'Паролі не збігаються'

        if errors:
            form = self.get_form()
            return render(request, self.template_name, {
                'errors': errors,
                'data': request.POST,
                'validlink': True,
                'form': form,
                'uid': kwargs.get('uidb64'),
                'token': kwargs.get('token'),
            })

        return super().post(request, *args, **kwargs)


# Універсальні сторінки університетів
# Про університет
def university_about(request, slug):
    uni = get_object_or_404(UniversityInfo, slug=slug)
    about = UniversityAbout.objects.filter(university=uni).first()
    profile = Profile.objects.filter(user=request.user).first() if request.user.is_authenticated else None
    return render(request, 'main/university_about.html', {
        'uni': uni, 'about': about, 'profile': profile,
    })


# Редагування інформації про університет
def university_about_edit(request, slug):
    uni = get_object_or_404(UniversityInfo, slug=slug)

    if not request.user.is_authenticated or \
       not hasattr(request.user, 'profile') or \
       request.user.profile.role != 'university_rep' or \
       request.user.profile.university_slug != slug:
        return redirect('university_about', slug=slug)

    about, _ = UniversityAbout.objects.get_or_create(university=uni)
    errors = {}

    if request.method == 'POST':
        title      = request.POST.get('title', '').strip()
        paragraphs = [request.POST.get(f'paragraph_{i}', '').strip() for i in range(1, 6)]

        if not title:
            errors['title'] = 'Назва не може бути порожньою'
        elif len(title) < 10:
            errors['title'] = 'Мінімум 10 символів'

        for i, p in enumerate(paragraphs, 1):
            if p and len(p) < 20:
                errors[f'paragraph_{i}'] = 'Мінімум 20 символів'

        if not errors:
            about.title = title
            for i, p in enumerate(paragraphs, 1):
                setattr(about, f'paragraph_{i}', p)
            about.save()
            return redirect('university_about', slug=slug)

    return render(request, 'main/university_about_edit.html', {
        'uni': uni, 'about': about, 'errors': errors,
    })


# Контакти університету
def university_contacts(request, slug):
    uni      = get_object_or_404(UniversityInfo, slug=slug)
    contacts = UniversityContacts.objects.filter(university=uni).first()
    profile  = Profile.objects.filter(user=request.user).first() if request.user.is_authenticated else None
    return render(request, 'main/university_contacts.html', {
        'uni': uni, 'contacts': contacts, 'profile': profile,
    })


# Редагування контактів університету
def university_contacts_edit(request, slug):
    uni = get_object_or_404(UniversityInfo, slug=slug)
    if not request.user.is_authenticated or \
       not hasattr(request.user, 'profile') or \
       request.user.profile.role != 'university_rep' or \
       request.user.profile.university_slug != slug:
        return redirect('university_contacts', slug=slug)
    contacts, _ = UniversityContacts.objects.get_or_create(university=uni)
    errors = {}
    if request.method == 'POST':
        address   = request.POST.get('address',   '').strip()
        phone_1   = request.POST.get('phone_1',   '').strip()
        phone_2   = request.POST.get('phone_2',   '').strip()
        email_pk  = request.POST.get('email_pk',  '').strip()
        email_uni = request.POST.get('email_uni', '').strip()
        youtube   = request.POST.get('youtube',   '').strip()
        telegram  = request.POST.get('telegram',  '').strip()
        if address and len(address) < 10:
            errors['address'] = 'Мінімум 10 символів'
        if phone_1 and len(phone_1) < 5:
            errors['phone_1'] = 'Некоректний номер'
        if phone_2 and len(phone_2) < 5:
            errors['phone_2'] = 'Некоректний номер'
        if not errors:
            contacts.address   = address
            contacts.phone_1   = phone_1
            contacts.phone_2   = phone_2
            contacts.email_pk  = email_pk
            contacts.email_uni = email_uni
            contacts.youtube   = youtube
            contacts.telegram  = telegram
            contacts.save()
            return redirect('university_contacts', slug=slug)
    return render(request, 'main/university_contacts_edit.html', {
        'uni': uni, 'contacts': contacts, 'errors': errors,
    })


# Веб-сайт університету
def university_website(request, slug):
    from .models import UniversityWebsite
    uni     = get_object_or_404(UniversityInfo, slug=slug)
    website = UniversityWebsite.objects.filter(university=uni).first()
    profile = Profile.objects.filter(user=request.user).first() if request.user.is_authenticated else None
    return render(request, 'main/university_website.html', {
        'uni': uni, 'website': website, 'profile': profile,
    })


# Редагування інформації про веб-сайт університету
def university_website_edit(request, slug):
    from .models import UniversityWebsite
    uni = get_object_or_404(UniversityInfo, slug=slug)
    if not request.user.is_authenticated or \
       not hasattr(request.user, 'profile') or \
       request.user.profile.role != 'university_rep' or \
       request.user.profile.university_slug != slug:
        return redirect('university_website', slug=slug)
    website, _ = UniversityWebsite.objects.get_or_create(university=uni)
    errors = {}
    if request.method == 'POST':
        site_url  = request.POST.get('site_url',  '').strip()
        image_url = request.POST.get('image_url', '').strip()
        if not site_url:
            errors['site_url'] = 'Посилання не може бути порожнім'
        if not errors:
            website.site_url  = site_url
            website.image_url = image_url
            website.save()
            return redirect('university_website', slug=slug)
    return render(request, 'main/university_website_edit.html', {
        'uni': uni, 'website': website, 'errors': errors,
    })


# Дати вступної кампанії
def university_dates(request, slug):
    from .models import UniversityDates
    uni   = get_object_or_404(UniversityInfo, slug=slug)
    dates = UniversityDates.objects.filter(university=uni).first()
    profile = Profile.objects.filter(user=request.user).first() if request.user.is_authenticated else None
    return render(request, 'main/university_dates.html', {
        'uni': uni, 'dates': dates, 'profile': profile,
        'july':    dates.get_july()    if dates else [],
        'august':  dates.get_august()  if dates else [],
        'sep_oct': dates.get_sep_oct() if dates else [],
    })


# Редагування дат вступної кампанії
def university_dates_edit(request, slug):
    from .models import UniversityDates
    import json
    uni = get_object_or_404(UniversityInfo, slug=slug)
    if not request.user.is_authenticated or \
       not hasattr(request.user, 'profile') or \
       request.user.profile.role != 'university_rep' or \
       request.user.profile.university_slug != slug:
        return redirect('university_dates', slug=slug)
    dates, _ = UniversityDates.objects.get_or_create(university=uni)
    if request.method == 'POST':
        def collect(prefix):
            items = []
            i = 1
            while request.POST.get(f'{prefix}_date_{i}'):
                items.append({
                    'date': request.POST.get(f'{prefix}_date_{i}', '').strip(),
                    'text': request.POST.get(f'{prefix}_text_{i}', '').strip(),
                })
                i += 1
            return json.dumps(items, ensure_ascii=False)
        dates.july    = collect('july')
        dates.august  = collect('august')
        dates.sep_oct = collect('sep_oct')
        dates.save()
        return redirect('university_dates', slug=slug)
    return render(request, 'main/university_dates_edit.html', {
        'uni': uni, 'dates': dates,
        'july':    dates.get_july(),
        'august':  dates.get_august(),
        'sep_oct': dates.get_sep_oct(),
    })


def university_programs(request, slug):
    uni = get_object_or_404(UniversityInfo, slug=slug)

    profile = None
    if request.user.is_authenticated and not request.user.is_superuser:
        profile = Profile.objects.filter(user=request.user).first()
    
    LETTER_NAMES = {
        'A': 'Освіта',
        'B': 'Культура і мистецтво',
        'C': 'Соціальні науки',
        'D': 'Бізнес і право',
        'E': 'Природничі науки',
        'F': 'ІТ сфера',
        'G': 'Інженерія',
        'H': 'Сільське господарство',
        'I': 'Соціальна сфера',
        'J': 'Сфера послуг',
        'K': 'Цивільна безпека',
        'S': 'Соціальні та економічні науки',
    }
    
    errors = {}
    data = {}
    avg = None
    show_rec = False
    recs = []
    btn_colors = {}
    now_date = ''
    now_time = ''
    fitting_specs_json = '[]'
    
    all_specialties = Specialty.objects.filter(
        university=uni
    ).exclude(min_score=None).exclude(high_score=None)
    
    # Збираємо літери + назви з бази, для кастомних беремо spec.name
    letter_name_map = {}
    for spec in Specialty.objects.filter(university=uni):
        if spec.code and spec.code[0].strip():
            letter = spec.code[0].upper()
            if letter not in letter_name_map:
                letter_name_map[letter] = LETTER_NAMES.get(letter, spec.name)

    LETTER_LABELS = {}
    for letter in sorted(letter_name_map):
        LETTER_LABELS[letter] = f'{letter} - {letter_name_map[letter]}'
    
    if request.method == "POST":
        data = request.POST
        scores = []
        fields = {
            'score_ukr': 'Українська мова',
            'score_math': 'Математика',
            'score_history': 'Історія України',
            'score_choice': 'Предмет на вибір',
        }
        
        for field, label in fields.items():
            val = data.get(field, '').strip()
            if not val:
                errors[field] = f'Введіть бал ({label})'
            else:
                try:
                    num = float(val)
                    if num < 100 or num > 200:
                        errors[field] = 'Бал повинен бути від 100 до 200'
                    else:
                        scores.append(num)
                except ValueError:
                    errors[field] = 'Введіть числове значення'
        
        if not errors:
            from collections import defaultdict
            avg = round(sum(scores) / len(scores), 1)
            show_rec = True
            now = datetime.now()
            now_date = now.strftime("%d.%m.%Y")
            now_time = now.strftime("%H:%M")
            
            groups = defaultdict(lambda: {'label': '', 'specs': []})
            for spec in all_specialties:
                if spec.code:
                    letter = spec.code[0].upper()
                    groups[letter]['label'] = LETTER_LABELS.get(letter, f'{letter} - Інше')
                    groups[letter]['specs'].append((spec.name, spec.min_score, spec.high_score))
            
            all_fitting = []
            for letter, group in sorted(groups.items()):
                if not group['specs']:
                    continue
                rec = _build_rec(letter, group, avg)
                recs.append(rec)
                btn_colors[letter] = rec['btn_color']
                for name, status in rec['specs_with_status']:
                    if status != 'red':
                        all_fitting.append({
                            'name': name,
                            'letter': letter,
                            'status': status,
                        })
            
            fitting_specs_json = json.dumps(all_fitting, ensure_ascii=False)

    btn_list = [
        {
            'letter': letter,
            'label': label,
            'color': btn_colors.get(letter, '#f2e7d5'),
        }
        for letter, label in LETTER_LABELS.items()
        if letter.strip()
    ]
    
    return render(request, 'main/university_programs.html', {
        'uni': uni,
        'uni_short_name': uni.abbr,
        'errors': errors,
        'data': data,
        'avg': avg,
        'show_rec': show_rec,
        'recs': recs,
        'btn_colors': btn_colors,
        'btn_list': btn_list,
        'now_date': now_date,
        'now_time': now_time,
        'fitting_specs_json': fitting_specs_json,
        'LETTER_LABELS': LETTER_LABELS,
        'profile': profile,
    })


# Допоміжні функції для рекомендацій, статус однієї спеціальності
def _spec_status(avg, min_score, high_score):
    if avg >= high_score:
        return 'green'
    elif avg >= min_score:
        return 'orange'
    return 'red'

# Повертає CSS background для кнопки шифру
def _btn_color(statuses):
    total  = len(statuses)
    green  = statuses.count('green')
    orange = statuses.count('orange')
    red    = statuses.count('red')

    COLOR = {
        'green':  'rgba(100, 180, 100, 0.70)',
        'orange': 'rgba(230, 160, 60,  0.70)',
        'red':    'rgba(200, 80,  80,  0.70)',
    }

    if green == total:
        return COLOR['green']
    if red == total:
        return COLOR['red']
    if orange == total:
        return COLOR['orange']

    # Мікс — пропорційний градієнт
    stops = []
    pct = 0
    step = 100 // total
    for s in statuses:
        stops.append(f"{COLOR[s]} {pct}%")
        pct += step
        stops.append(f"{COLOR[s]} {pct}%")
    return f"linear-gradient(135deg, {', '.join(stops)})"

# Будує словник рекомендації для одного шифру
def _build_rec(letter, group, avg):
    specs    = group['specs']
    statuses = [_spec_status(avg, mn, hi) for _, mn, hi in specs]

    green  = statuses.count('green')
    orange = statuses.count('orange')
    red    = statuses.count('red')
    total  = len(specs)
    label  = group['label']

    # Текст пояснення
    if green == total:
        summary = (
            f"Ваш середній бал НМТ ({avg}) перевищує поріг високих шансів "
            f"для всіх спеціальностей галузі «{label}» — рекомендуємо розглядати "
            f"цю галузь як пріоритетну."
        )
    elif red == total:
        summary = (
            f"На жаль, ваш середній бал НМТ ({avg}) є нижчим за мінімальний поріг "
            f"для всіх спеціальностей галузі «{label}». "
            f"Радимо розглянути галузі з нижчими вимогами."
        )
    elif orange == total:
        summary = (
            f"Ваш бал ({avg}) відповідає мінімальним вимогам для всіх спеціальностей "
            f"галузі «{label}», але до порогу високих шансів ще є простір. "
            f"Подавати документи можна, однак конкуренція буде відчутною."
        )
    elif green > red:
        fit_names = [n for (n, _, _), st in zip(specs, statuses) if st == 'green']
        summary = (
            f"Більшість спеціальностей галузі «{label}» підходять вам за балом ({avg}). "
            f"Найвищі шанси: {', '.join(fit_names)}."
        )
    elif red > green:
        ok_names = [n for (n, _, _), st in zip(specs, statuses) if st in ('green', 'orange')]
        if ok_names:
            summary = (
                f"Більшість спеціальностей галузі «{label}» потребують вищого балу ніж у вас ({avg}). "
                f"Проте можна розглянути: {', '.join(ok_names)}."
            )
        else:
            summary = (
                f"Більшість спеціальностей галузі «{label}» потребують вищого балу ніж у вас ({avg}). "
                f"Радимо розглянути інші галузі."
            )
    else:
        # рівно навпіл
        ok_names = [n for (n, _, _), st in zip(specs, statuses) if st in ('green', 'orange')]
        summary = (
            f"Рівно половина спеціальностей галузі «{label}» підходять за вашим балом ({avg}), "
            f"половина — ні. Уважно оберіть конкретну спеціальність. "
            f"Варіанти: {', '.join(ok_names)}."
        )

    return {
        'letter':           letter,
        'label':            label,
        'summary':          summary,
        'btn_color':        _btn_color(statuses),
        'specs_with_status': list(zip([n for n, _, _ in specs], statuses)),
        'count_total':      total,
        'count_fit':        green + orange,
    }


def save_recommendation(request):
    if request.method == "POST" and request.user.is_authenticated:
        avg        = request.POST.get('avg')
        university = request.POST.get('university', 'ХНЕУ імені Семена Кузнеця')
        specs_json = request.POST.get('fitting_specs', '[]')

        # Максимум 10 рекомендацій
        existing = SavedRecommendation.objects.filter(user=request.user)
        if existing.count() >= 10:
            return redirect('saved_recommendations')

        rec = SavedRecommendation(
            user=request.user,
            university=university,
            avg_score=float(avg.replace(',', '.')),
        )
        rec.set_fitting_specs(json.loads(specs_json))
        rec.save()

    return redirect('saved_recommendations')


def delete_recommendation(request, rec_id):
    if request.user.is_authenticated:
        SavedRecommendation.objects.filter(id=rec_id, user=request.user).delete()
    return redirect('saved_recommendations')


def clear_recommendations(request):
    if request.user.is_authenticated:
        SavedRecommendation.objects.filter(user=request.user).delete()
    return redirect('saved_recommendations')


def saved_recommendations(request):
    recs = SavedRecommendation.objects.filter(user=request.user)
    recs_data = []
    for i, rec in enumerate(recs, 1):
        recs_data.append({
            'id':       rec.id,
            'number':   i,
            'date':     rec.created_at.strftime("%d.%m.%Y"),
            'time':     rec.created_at.strftime("%H:%M"),
            'university': rec.university,
            'avg_score':  rec.avg_score,
            'fitting_specs': rec.get_fitting_specs(),
            'count': len(rec.get_fitting_specs()),
        })
    return render(request, 'main/saved_recommendations.html', {
        'recs': recs_data,
        'total': len(recs_data),
    })


# Сторінка зі спеціальностями певної галузі
def university_programs_letter(request, slug, letter):
    uni = get_object_or_404(UniversityInfo, slug=slug)
    specialties = Specialty.objects.filter(
        university=uni,
        code__startswith=letter.upper()
    ).exclude(code=letter.upper())

    PROGRAMS_URLS = {
    'hneu':  'hneu_programs',
    'hnure': 'hnure_programs',
    'hpi':   'hpi_programs',
    'hnu':   'hnu_programs',
    'hnumg': 'hnumg_programs',
}

    programs_url_name = PROGRAMS_URLS.get(slug, 'universities')

    return render(request, 'main/university_programs_letter.html', {
    'uni':          uni,
    'specialties':  specialties,
    'letter':       letter,
    'programs_url': programs_url_name,
    'slug':         slug,
})


LETTER_NAMES = {
    'A': 'Освіта',
    'B': 'Культура і мистецтво',
    'C': 'Соціальні науки',
    'D': 'Бізнес і право',
    'E': 'Природничі науки',
    'F': 'ІТ сфера',
    'G': 'Інженерія',
    'H': 'Сільське господарство',
    'I': 'Соціальна сфера',
    'J': 'Сфера послуг',
    'K': 'Цивільна безпека',
    'S': 'Соціальні та економічні науки',
}


# Сторінка створення нової галузі (шифру) для університету
def university_program_create(request, slug):
    uni = get_object_or_404(UniversityInfo, slug=slug)

    if not request.user.is_authenticated or \
       not hasattr(request.user, 'profile') or \
       request.user.profile.role != 'university_rep' or \
       request.user.profile.university_slug != slug:
        return redirect('university_detail', slug=slug)

    LETTER_NAMES = {
        'A': 'Освіта',
        'B': 'Культура і мистецтво',
        'C': 'Соціальні науки',
        'D': 'Бізнес і право',
        'E': 'Природничі науки',
        'F': 'ІТ сфера',
        'G': 'Інженерія',
        'H': 'Сільське господарство',
        'I': 'Соціальна сфера',
        'J': 'Сфера послуг',
        'K': 'Цивільна безпека',
        'S': 'Соціальні та економічні науки',
    }

    errors = {}

    if request.method == 'POST':
        letter        = request.POST.get('letter',        '').strip().upper()
        custom_letter = request.POST.get('custom_letter', '').strip().upper()
        custom_name   = request.POST.get('custom_name',   '').strip()

        if not letter:
            errors['letter'] = 'Оберіть галузь'

        elif letter == 'OTHER':
            if not custom_letter:
                errors['custom_letter'] = 'Введіть букву галузі'
            elif len(custom_letter) != 1 or not custom_letter.isalpha():
                errors['custom_letter'] = 'Має бути одна літера'
            elif custom_letter in LETTER_NAMES:
                errors['custom_letter'] = 'Ця буква вже є у стандартному списку — оберіть її зі списку вище'
            elif Specialty.objects.filter(university=uni, code=custom_letter).exists():
                errors['custom_letter'] = f'Галузь "{custom_letter}" вже існує в цьому університеті'

            if not custom_name:
                errors['custom_name'] = 'Введіть назву галузі'
            elif len(custom_name) < 3:
                errors['custom_name'] = 'Мінімум 3 символи'

            if not errors:
                # Створюємо галузь 
                Specialty.objects.create(
                    university=uni,
                    code=custom_letter,
                    name=custom_name,
                )
                return redirect('university_programs', slug=slug)

        else:
            if letter not in LETTER_NAMES:
                errors['letter'] = 'Невірна галузь'
            elif Specialty.objects.filter(university=uni, code=letter).exists():
                errors['letter'] = f'Галузь "{letter} — {LETTER_NAMES[letter]}" вже існує в цьому університеті'
            else:
                Specialty.objects.create(
                    university=uni,
                    code=letter,
                    name=LETTER_NAMES[letter],
                )
                return redirect('university_programs', slug=slug)  # ← назад до списку галузей

    return render(request, 'main/university_program_create.html', {
        'uni': uni,
        'errors': errors,
        'data': request.POST if request.method == 'POST' else {},
    })


# Сторінка видалення галузі (шифру) для університету
def university_program_delete(request, slug, letter):
    uni = get_object_or_404(UniversityInfo, slug=slug)

    if not request.user.is_authenticated or \
       not hasattr(request.user, 'profile') or \
       request.user.profile.role != 'university_rep' or \
       request.user.profile.university_slug != slug:
        return redirect('universities')

    Specialty.objects.filter(university=uni, code__startswith=letter.upper()).delete()
    return redirect('university_programs', slug=slug)


# Сторінка створення нової спеціальності для певного університету та галузі
def specialty_create(request, slug):
    uni = get_object_or_404(UniversityInfo, slug=slug)

    if not request.user.is_authenticated or \
       not hasattr(request.user, 'profile') or \
       request.user.profile.role != 'university_rep' or \
       request.user.profile.university_slug != slug:
        return redirect('universities')

    errors = {}

    if request.method == 'POST':
        code          = request.POST.get('code',          '').strip()
        name          = request.POST.get('name',          '').strip()
        about         = request.POST.get('about',         '').strip()
        what_to_study = request.POST.get('what_to_study', '').strip()
        career        = request.POST.get('career',        '').strip()
        min_score     = request.POST.get('min_score',     '').strip()
        high_score    = request.POST.get('high_score',    '').strip()

        if not name:
            errors['name'] = 'Назва не може бути порожньою'
        elif len(name) < 5:
            errors['name'] = 'Мінімум 5 символів'

        if about and len(about) < 20:
            errors['about'] = 'Мінімум 20 символів'
        if what_to_study and len(what_to_study) < 20:
            errors['what_to_study'] = 'Мінімум 20 символів'
        if career and len(career) < 20:
            errors['career'] = 'Мінімум 20 символів'

        if min_score:
            try:
                min_score_val = float(min_score)
                if not (100 <= min_score_val <= 200):
                    errors['min_score'] = 'Бал має бути від 100 до 200'
            except ValueError:
                errors['min_score'] = 'Введіть коректне число'
        else:
            min_score_val = None

        if high_score:
            try:
                high_score_val = float(high_score)
                if not (100 <= high_score_val <= 200):
                    errors['high_score'] = 'Бал має бути від 100 до 200'
            except ValueError:
                errors['high_score'] = 'Введіть коректне число'
        else:
            high_score_val = None

        if Specialty.objects.filter(university=uni, name=name).exists():
            errors['name'] = 'Спеціальність з такою назвою вже існує'

        if not errors:
            Specialty.objects.create(
                university=uni,
                code=code,
                name=name,
                about=about,
                what_to_study=what_to_study,
                career=career,
                min_score=min_score_val,
                high_score=high_score_val,
            )
            return redirect('university_programs_letter', slug=slug, letter=code[0] if code else 'A')

    return render(request, 'main/university_specialty_create.html', {
        'uni': uni,
        'errors': errors,
        'data': request.POST if request.method == 'POST' else {},
    })


# Редагування спеціальності для певного університету
def specialty_edit(request, slug, specialty_id):
    uni = get_object_or_404(UniversityInfo, slug=slug)

    if not request.user.is_authenticated or \
       not hasattr(request.user, 'profile') or \
       request.user.profile.role != 'university_rep' or \
       request.user.profile.university_slug != slug:
        return redirect('universities')

    specialty = get_object_or_404(Specialty, id=specialty_id, university=uni)
    errors = {}

    if request.method == 'POST':
        code          = request.POST.get('code',          '').strip()
        name          = request.POST.get('name',          '').strip()
        about         = request.POST.get('about',         '').strip()
        what_to_study = request.POST.get('what_to_study', '').strip()
        career        = request.POST.get('career',        '').strip()
        min_score     = request.POST.get('min_score',     '').strip()
        high_score    = request.POST.get('high_score',    '').strip()

        if not name:
            errors['name'] = 'Назва не може бути порожньою'
        elif len(name) < 5:
            errors['name'] = 'Мінімум 5 символів'

        if about and len(about) < 20:
            errors['about'] = 'Мінімум 20 символів'
        if what_to_study and len(what_to_study) < 20:
            errors['what_to_study'] = 'Мінімум 20 символів'
        if career and len(career) < 20:
            errors['career'] = 'Мінімум 20 символів'

        if min_score:
            try:
                min_score_val = float(min_score)
                if not (100 <= min_score_val <= 200):
                    errors['min_score'] = 'Бал має бути від 100 до 200'
            except ValueError:
                errors['min_score'] = 'Введіть коректне число'
        else:
            min_score_val = None

        if high_score:
            try:
                high_score_val = float(high_score)
                if not (100 <= high_score_val <= 200):
                    errors['high_score'] = 'Бал має бути від 100 до 200'
            except ValueError:
                errors['high_score'] = 'Введіть коректне число'
        else:
            high_score_val = None

        if not errors:
            specialty.code          = code
            specialty.name          = name
            specialty.about         = about
            specialty.what_to_study = what_to_study
            specialty.career        = career
            specialty.min_score     = min_score_val
            specialty.high_score    = high_score_val
            specialty.save()
            letter = code[0].upper() if code else specialty.code[0].upper()
            return redirect('university_programs_letter', slug=slug, letter=letter)

    return render(request, 'main/university_specialty_edit.html', {
        'uni':       uni,
        'specialty': specialty,
        'errors':    errors,
        'letter':    specialty.code[0].upper() if specialty.code else 'A',
    })

# Видалення спеціальності для певного університету
def specialty_delete(request, slug, specialty_id):
    uni = get_object_or_404(UniversityInfo, slug=slug)

    if not request.user.is_authenticated or \
       not hasattr(request.user, 'profile') or \
       request.user.profile.role != 'university_rep' or \
       request.user.profile.university_slug != slug:
        return redirect('universities')

    specialty = get_object_or_404(Specialty, id=specialty_id, university=uni)
    letter = specialty.code[0].upper() if specialty.code else 'A'
    specialty.delete()
    return redirect('university_programs_letter', slug=slug, letter=letter)


@user_passes_test(is_admin, login_url='home')
def admin_university_create(request):
    errors = {}

    if UniversityInfo.objects.count() >= 9:
        errors['limit'] = 'Перевищено максимальну кількість університетів (максимум 9)'

    if request.method == 'POST':
        slug      = request.POST.get('slug', '').strip().lower()
        abbr      = request.POST.get('abbr', '').strip().upper()
        full_name = request.POST.get('full_name', '').strip()
        photo_url = request.POST.get('photo_url', '').strip()

        if not slug:
            errors['slug'] = 'Slug не може бути порожнім'
        elif not re.fullmatch(r'[a-z0-9\-]+', slug):
            errors['slug'] = 'Тільки латинські літери, цифри та дефіс'
        elif UniversityInfo.objects.filter(slug=slug).exists():
            errors['slug'] = 'Університет з таким slug вже існує'

        if not abbr:
            errors['abbr'] = 'Абревіатура не може бути порожньою'
        elif len(abbr) < 2 or len(abbr) > 10:
            errors['abbr'] = 'Від 2 до 10 символів'

        if not full_name:
            errors['full_name'] = 'Назва не може бути порожньою'
        elif len(full_name) < 20:
            errors['full_name'] = 'Мінімум 20 символів'

        if not errors:
            uni = UniversityInfo.objects.create(
                slug=slug,
                abbr=abbr,
                full_name=full_name,
                photo_url=photo_url,
            )
            # Автоматично створюємо порожні записи для всіх вкладок
            UniversityAbout.objects.create(university=uni, title=full_name)
            from .models import UniversityContacts, UniversityDates, UniversityWebsite
            UniversityContacts.objects.create(university=uni)
            UniversityDates.objects.create(university=uni)
            UniversityWebsite.objects.create(university=uni)

            return redirect('universities')

    return render(request, 'main/admin_university_create.html', {
        'errors': errors,
        'data': request.POST,
    })


# Посвідчення
@user_passes_test(is_admin, login_url='home')
def admin_credentials(request):
    if request.method == 'POST':
        cred_id = request.POST.get('credential_id')
        action  = request.POST.get('action')
        if action == 'delete_credential' and cred_id:
            ValidCredential.objects.filter(id=cred_id).delete()
        return redirect('admin_credentials')

    credentials = ValidCredential.objects.all().order_by('-id')
    return render(request, 'main/admin_credentials.html', {'credentials': credentials})


@user_passes_test(is_admin, login_url='home')
def admin_credential_create(request):
    errors = {}

    if request.method == 'POST':
        university_code   = request.POST.get('university_code', '').strip().upper()
        credential_number = request.POST.get('credential_number', '').strip()

        if not university_code:
            errors['university_code'] = 'Введіть абревіатуру університету'
        elif not re.fullmatch(r'[A-ZА-ЯІЇЄ]{2,10}', university_code):
            errors['university_code'] = 'Тільки літери, від 2 до 10 символів'

        if not credential_number:
            errors['credential_number'] = 'Введіть номер посвідчення'
        elif not re.fullmatch(r'\d{12}', credential_number):
            errors['credential_number'] = 'Рівно 12 цифр'
        elif ValidCredential.objects.filter(
            university_code=university_code,
            credential_number=credential_number
        ).exists():
            errors['credential_number'] = 'Таке посвідчення вже існує'

        if not errors:
            ValidCredential.objects.create(
                university_code=university_code,
                credential_number=credential_number,
                is_used=False
            )
            return redirect('admin_credentials')

    return render(request, 'main/admin_credential_create.html', {
        'errors': errors,
        'data': request.POST,
    })


# КОРИСТУВАЧІ СИСТЕМИ
@user_passes_test(is_admin, login_url='home')
def admin_users(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        action_type = request.POST.get('action_type')

        target = User.objects.filter(id=user_id).first()

        if target and not target.is_superuser:

            # Блокування користувача
            if action_type == 'block':
                target.is_active = False
                target.save()

                AdminAction.objects.create(
                    admin=request.user,
                    target_user=target,
                    action_type='block'
                )

            # Розблокування користувача
            elif action_type == 'unblock':
                target.is_active = True
                target.save()

                AdminAction.objects.create(
                    admin=request.user,
                    target_user=target,
                    action_type='unblock'
                )

            # Видалення користувача
            elif action_type == 'delete':

                # Лог дії адміністратора
                AdminAction.objects.create(
                    admin=request.user,
                    target_user=target,
                    action_type='delete'
                )

                # Отримуємо профіль користувача
                profile = Profile.objects.filter(user=target).first()

                # Якщо є посвідчення — звільняємо його
                if profile and profile.id_prefix and profile.id_number:

                    credential = ValidCredential.objects.filter(
                        university_code=profile.id_prefix,
                        credential_number=profile.id_number
                    ).first()

                    if credential:
                        credential.is_used = False
                        credential.save()

                # Видаляємо користувача
                target.delete()

        return redirect('admin_users')

    # Всі користувачі, окрім адміністраторів
    users = User.objects.filter(is_superuser=False).select_related('profile').order_by('id')

    return render(request, 'main/admin_users.html', {
        'users': users
    })


def university_delete(request, slug):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return redirect('universities')

    uni = get_object_or_404(UniversityInfo, slug=slug)
    uni.delete()
    return redirect('universities')