# -*- coding: utf-8 -*-

from django import forms

class MyForm(forms.ModelForm):

    class Meta:
        model = MyModel

