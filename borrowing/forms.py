# borrowing/forms.py

from django import forms
from .models import Item

class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['name', 'description', 'quantity']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }