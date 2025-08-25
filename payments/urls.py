from django.urls import path
from .views import (
    CreatePaymentView,
    PaymentStatusView,
    PaymentCallbackView,
    PaymentListView,TestMoyasarView
)

urlpatterns = [
    path('create-payment/', CreatePaymentView.as_view(), name='create_payment'),
    path('payment-status/<int:payment_id>/', PaymentStatusView.as_view(), name='payment_status'),
    path('callback/', PaymentCallbackView.as_view(), name='payment_callback'),
    path('payments/', PaymentListView.as_view(), name='payment_list'),
    path('test-moyasar/', TestMoyasarView.as_view(), name='test_moyasar'),

]