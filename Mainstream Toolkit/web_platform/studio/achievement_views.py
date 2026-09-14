from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from .achievements import progress
from .models import ProfileUnlock

class ShowcaseForm(forms.Form):
    badge=forms.ChoiceField(required=False,label='Public profile badge')
    show_scene=forms.BooleanField(required=False,label='Show my selected scene on my public profile')
    scene=forms.TypedChoiceField(coerce=int,label='Public profile scene')

@login_required
@never_cache
@require_http_methods(['GET','POST'])
def achievements(request):
    journey=progress(request.user)
    pref=ProfileUnlock.objects.filter(user=request.user).first()
    form=ShowcaseForm(request.POST if request.method=='POST' else None,initial={'badge':pref.badge if pref else '', 'show_scene':pref.show_scene if pref else False,'scene':pref.scene if pref else 0})
    form.fields['badge'].choices=[('','No public badge')]+[(c['code'],c['title']) for c in journey['cards'] if c['unlocked']]
    form.fields['scene'].choices=[(s['level'],s['name']) for s in journey['stages'] if s['unlocked']]
    if request.method=='POST' and form.is_valid():
        ProfileUnlock.objects.update_or_create(user=request.user,defaults=form.cleaned_data)
        messages.success(request,'Your public profile showcase has been updated.')
        return redirect('achievements')
    return render(request,'community/achievements.html',{'journey':journey,'showcase_form':form})
