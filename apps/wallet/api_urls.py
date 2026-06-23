"""Wallet API URLs"""
from django.urls import path
from apps.wallet import views

urlpatterns = [
    path("", views.WalletView.as_view(), name="api-wallet"),
    path("transactions/", views.TransactionListView.as_view(), name="api-transactions"),
    path("withdraw/", views.WithdrawalListCreateView.as_view(), name="api-withdraw"),
    path("withdraw/<uuid:pk>/", views.WithdrawalDetailView.as_view(), name="api-withdraw-detail"),
    path("rates/", views.EarningRateListView.as_view(), name="api-earning-rates"),
    path("earnings/summary/", views.EarningsSummaryView.as_view(), name="api-earnings-summary"),
    path("recharge/operators/", views.RechargeOperatorListCreateView.as_view(), name="api-recharge-operators"),
    path("recharge/operators/<int:pk>/", views.RechargeOperatorDetailView.as_view(), name="api-recharge-operator-detail"),
    path("recharge/plans/", views.RechargePlanListCreateView.as_view(), name="api-recharge-plans"),
    path("recharge/plans/<int:pk>/", views.RechargePlanDetailView.as_view(), name="api-recharge-plan-detail"),
    path("recharge/orders/", views.RechargeOrderListView.as_view(), name="api-recharge-orders"),
    path("recharge/orders/create/", views.RechargeOrderCreateView.as_view(), name="api-recharge-order-create"),
]
