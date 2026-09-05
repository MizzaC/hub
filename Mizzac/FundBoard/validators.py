"""Reusable validators for canonical financial identifiers."""

from django.core.exceptions import ValidationError


def validate_currency_code(value):
    if value and (len(value) != 3 or not value.isascii() or not value.isalpha()):
        raise ValidationError("Utilisez un code devise ISO sur trois lettres.")


def validate_country_code(value):
    if value and (len(value) != 2 or not value.isascii() or not value.isalpha()):
        raise ValidationError("Utilisez un code pays ISO sur deux lettres.")
