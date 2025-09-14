from django.urls import path
from .views import CreatePaymentView, fetch_payment_view,ListPaymentsView,refund_payment_view,payment_callback_view,invoice_detail_view,all_invoices_view,payment_redirect_view

urlpatterns = [
    path("create/", CreatePaymentView.as_view(), name="create-payment"),
    path('fetch/<str:moyasar_id>/', fetch_payment_view, name='fetch-payment'),
    path('list/', ListPaymentsView.as_view(), name='list-payments'),
    path("refund/<str:moyasar_id>/", refund_payment_view, name="refund-payment"),  
    path('callback/', payment_callback_view, name='payment-callback'),
    path("redirect/", payment_redirect_view, name="payment_redirect"),  # GET
    path('invoice/<str:moyasar_id>/', invoice_detail_view, name='invoice-detail'),
    path('invoices/', all_invoices_view, name='all-invoices'),
    
]
