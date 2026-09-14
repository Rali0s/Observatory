from django import forms
from urllib.parse import urlsplit

class EditionForm(forms.Form):
    edition_name = forms.CharField(max_length=120, initial='First edition')
    description = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={'rows':3}), required=False)
    attributes = forms.JSONField(required=False, initial=dict, help_text='Optional JSON object, e.g. {"language": "English", "edition": "1 of 1"}.')
    sat_mode = forms.ChoiceField(choices=[('regular','Regular mint · Xverse'),('special','Special / rare sat · Gamma')])
    requested_sat = forms.IntegerField(min_value=0, max_value=2099999997689999, required=False, label='Exact sat number (special sats)')
    consent = forms.BooleanField(label='I own the rights and approve making this edition and its metadata permanently public on Bitcoin. Wallet fees are separate from membership.')

    def clean_attributes(self):
        value = self.cleaned_data.get('attributes') or {}
        if not isinstance(value, dict) or len(value)>20 or any(not isinstance(k,str) or len(k)>60 or not isinstance(v,(str,int,bool)) or len(str(v))>240 for k,v in value.items()):
            raise forms.ValidationError('Use up to 20 short text, integer or boolean attributes.')
        return value

    def clean(self):
        data = super().clean()
        if data.get('sat_mode')=='special' and data.get('requested_sat') is None:
            self.add_error('requested_sat','Choose the exact sat number you will use on Gamma.')
        return data

class InscriptionForm(forms.Form):
    inscription_id = forms.RegexField(r'^[0-9a-f]{64}i[0-9]{1,9}$', max_length=80, label='Inscription ID')

class ListingForm(forms.Form):
    marketplace_url = forms.URLField(max_length=500, required=False, label='Your Gamma listing URL')
    def clean_marketplace_url(self):
        url = self.cleaned_data['marketplace_url']
        if not url: return ''
        try:
            parts = urlsplit(url)
            port = parts.port
        except ValueError:
            raise forms.ValidationError('Use a valid Gamma listing URL.')
        if parts.scheme!='https' or parts.hostname not in ('gamma.io','www.gamma.io') or parts.username or parts.password or port not in (None,443) or parts.path in ('','/'):
            raise forms.ValidationError('Use a specific HTTPS listing on gamma.io.')
        return url
