from django.urls import path
from .views import (
    CreatePaymentView, 
    fetch_payment_view,
    ListPaymentsView,
    refund_payment_view,
    payment_callback_view,
    invoice_detail_view,
    all_invoices_view,
    user_invoices_view,
    moyasar_webhook,
    display_invoice_view,
    test_callback_view,payment_page
)

urlpatterns = [
    path("create/", CreatePaymentView.as_view(), name="create-payment"),
    path("pay/", payment_page, name="payment_page"),
    path('fetch/<str:moyasar_id>/', fetch_payment_view, name='fetch-payment'),
    path('list/', ListPaymentsView.as_view(), name='list-payments'),
    path("refund/<str:moyasar_id>/", refund_payment_view, name="refund-payment"),
    
    # Callback and webhook endpoints
    path('callback/', payment_callback_view, name='payment-callback'),
    path('webhook/', moyasar_webhook, name='moyasar-webhook'),
    path('test-callback/', test_callback_view, name='test-callback'),
    
    # Invoice endpoints
    path('invoice/<str:moyasar_id>/', invoice_detail_view, name='invoice-detail'),
    path('invoices/', all_invoices_view, name='all-invoices'),
    path('my-invoices/', user_invoices_view, name='user-invoices'),
    
    # Invoice display and download
    path('invoice/<str:moyasar_id>/display/', display_invoice_view, name='invoice-display'),
]