from django.urls import path
from .views import (
    ToolBoardView,
    ToolDetailView,
    IPCalculatorView,
    CurrencyConverterView,
    VATCalculatorView,
    PasswordGeneratorView,
    Base64ConverterView,
)

app_name = 'toolboard'

urlpatterns = [
    path('', ToolBoardView.as_view(), name='toolboard'),
    path('ip-calculator/', IPCalculatorView.as_view(), name='ip_calculator'),
    path('currency-converter/', CurrencyConverterView.as_view(), name='currency_converter'),
    path('vat-calculator/', VATCalculatorView.as_view(), name='vat_calculator'),
    path('password-generator/', PasswordGeneratorView.as_view(), name='password_generator'),
    path('base64-converter/', Base64ConverterView.as_view(), name='base64_converter'),
    path('<slug:slug>/', ToolDetailView.as_view(), name='tool_detail'),
]
