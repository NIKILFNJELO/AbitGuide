from .models import Profile

def profile_processor(request):
    if request.user.is_authenticated:
        profile = Profile.objects.filter(user=request.user).first()
    else:
        profile = None

    return {
        "profile": profile
    }