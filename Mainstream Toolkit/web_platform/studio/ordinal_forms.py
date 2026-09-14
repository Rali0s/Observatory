from django import forms
from urllib.parse import urlsplit

class EditionForm(forms.Form):
    edition_name = forms.CharField(max_length=120, initial='First edition')
    description = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={'rows':3}), required=False)
    collection = forms.CharField(max_length=120, required=False, label='Collection (optional)')
    language = forms.CharField(max_length=60, required=False, initial='English')
    genre = forms.CharField(max_length=60, required=False, label='Genre (optional)')
    sat_mode = forms.ChoiceField(choices=[('regular','Regular mint · Xverse'),('special','Choose a rare sat · Gamma')],widget=forms.RadioSelect, initial='regular')
    sat_choice = forms.CharField(max_length=2000, required=False, widget=forms.Select(choices=[('', 'Load your wallet to choose a sat')]),label='Choose a sat from your wallet')
    consent = forms.BooleanField(label='I own the rights and approve making this edition and its metadata permanently public on Bitcoin. Wallet fees are separate from membership.')

    def __init__(self,*args,user=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.user=user
        if self.is_bound and self.data.get('sat_choice'):
            self.fields['sat_choice'].widget.choices=[(self.data['sat_choice'],'Previously selected sat — reload wallet to change')]

    def clean(self):
        data=super().clean()
        attributes={k:data[k] for k in ['collection','language','genre'] if data.get(k)}
        keys=self.data.getlist('trait_name') if hasattr(self.data,'getlist') else self.data.get('trait_name',[])
        values=self.data.getlist('trait_value') if hasattr(self.data,'getlist') else self.data.get('trait_value',[])
        if not isinstance(keys,list) or not isinstance(values,list) or len(keys)!=len(values) or len(keys)>17:
            raise forms.ValidationError('Add up to 17 matching trait names and values.')
        for key,value in zip(keys,values):
            key,value=key.strip(),value.strip()
            if not key and not value:continue
            if not key or not value or len(key)>60 or len(value)>240:
                raise forms.ValidationError('Each trait needs a name (up to 60 characters) and value (up to 240).')
            if key.casefold() in {name.casefold() for name in attributes}:
                raise forms.ValidationError('Use a different name for each trait.')
            attributes[key]=value
        data['attributes']=attributes
        data['requested_sat']=None
        if data.get('sat_mode')=='special':
            if not data.get('sat_choice'):
                self.add_error('sat_choice','Load your wallet and choose an available rare sat.')
            elif self.user:
                from .rare_sats import selection
                try:
                    data['selected_sat']=selection(self.user,data['sat_choice'])
                    data['requested_sat']=data['selected_sat']['sat']
                except Exception:
                    self.add_error('sat_choice','The selected sat could not be verified. Load your wallet sats again.')
            else:
                self.add_error('sat_choice','Sign in to choose a wallet sat.')
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
