"""
URL Configuration for Hostel Management API.

All API routing with kebab-case paths and named URLs.
"""

from django.urls import path
from . import views

app_name = 'hostel_management_api'

urlpatterns = [
    # ══════════════════════════════════════════════════════════════
    # HALL ENDPOINTS
    # ══════════════════════════════════════════════════════════════
    path('halls/', views.list_halls, name='list-halls'),
    path('halls/<int:hall_id>/', views.get_hall, name='get-hall'),
    path('halls/create/', views.create_hall, name='create-hall'),
    path('halls/<int:hall_id>/delete/', views.delete_hall, name='delete-hall'),

    # ══════════════════════════════════════════════════════════════
    # CARETAKER & WARDEN ENDPOINTS
    # ══════════════════════════════════════════════════════════════
    path('caretakers/assign/', views.assign_caretaker, name='assign-caretaker'),
    path('wardens/assign/', views.assign_warden, name='assign-warden'),
    path('batches/assign/', views.assign_batch, name='assign-batch'),

    # ══════════════════════════════════════════════════════════════
    # GUEST ROOM BOOKING ENDPOINTS
    # ══════════════════════════════════════════════════════════════
    path('bookings/create/', views.create_booking, name='create-booking'),
    path('bookings/', views.list_bookings, name='list-bookings'),
    path('bookings/my/', views.my_bookings, name='my-bookings'),
    path('bookings/approve/', views.approve_booking, name='approve-booking'),
    path('bookings/<int:booking_id>/reject/', views.reject_booking, name='reject-booking'),

    # ══════════════════════════════════════════════════════════════
    # GUEST ROOM ENDPOINTS
    # ══════════════════════════════════════════════════════════════
    path('guest-rooms/hall/<int:hall_id>/', views.list_guest_rooms, name='list-guest-rooms'),

    # ══════════════════════════════════════════════════════════════
    # NOTICE ENDPOINTS
    # ══════════════════════════════════════════════════════════════
    path('notices/', views.list_notices, name='list-notices'),
    path('notices/create/', views.create_notice, name='create-notice'),
    path('notices/<int:notice_id>/delete/', views.delete_notice, name='delete-notice'),

    # ══════════════════════════════════════════════════════════════
    # LEAVE ENDPOINTS
    # ══════════════════════════════════════════════════════════════
    path('leaves/create/', views.create_leave, name='create-leave'),
    path('leaves/', views.list_leaves, name='list-leaves'),
    path('leaves/my/', views.my_leaves, name='my-leaves'),
    path('leaves/update-status/', views.update_leave_status, name='update-leave-status'),

    # ══════════════════════════════════════════════════════════════
    # COMPLAINT ENDPOINTS
    # ══════════════════════════════════════════════════════════════
    path('complaints/file/', views.file_complaint, name='file-complaint'),
    path('complaints/', views.list_complaints, name='list-complaints'),
    path('complaints/my/', views.my_complaints, name='my-complaints'),

    # ══════════════════════════════════════════════════════════════
    # FINE ENDPOINTS
    # ══════════════════════════════════════════════════════════════
    path('fines/impose/', views.impose_fine, name='impose-fine'),
    path('fines/', views.list_fines, name='list-fines'),
    path('fines/my/', views.my_fines, name='my-fines'),
    path('fines/<int:fine_id>/update/', views.update_fine, name='update-fine'),
    path('fines/<int:fine_id>/delete/', views.delete_fine, name='delete-fine'),

    # ══════════════════════════════════════════════════════════════
    # INVENTORY ENDPOINTS
    # ══════════════════════════════════════════════════════════════
    path('inventory/create/', views.create_inventory, name='create-inventory'),
    path('inventory/hall/<int:hall_id>/', views.list_inventory, name='list-inventory'),
    path('inventory/<int:inventory_id>/update/', views.update_inventory, name='update-inventory'),
    path('inventory/<int:inventory_id>/delete/', views.delete_inventory, name='delete-inventory'),

    # ══════════════════════════════════════════════════════════════
    # ATTENDANCE ENDPOINTS
    # ══════════════════════════════════════════════════════════════
    path('attendance/mark/', views.mark_attendance, name='mark-attendance'),
    path('attendance/hall/<int:hall_id>/', views.list_attendance, name='list-attendance'),

    # ══════════════════════════════════════════════════════════════
    # ROOM MANAGEMENT ENDPOINTS
    # ══════════════════════════════════════════════════════════════
    path('rooms/hall/<int:hall_id>/', views.list_rooms, name='list-rooms'),
    path('rooms/change/', views.change_room, name='change-room'),

    # ══════════════════════════════════════════════════════════════
    # HISTORY ENDPOINTS
    # ══════════════════════════════════════════════════════════════
    path('history/transactions/', views.list_transaction_history, name='list-transaction-history'),
    path('history/hostel/', views.list_hostel_history, name='list-hostel-history'),

    # ══════════════════════════════════════════════════════════════
    # USER ROLE ENDPOINT
    # ══════════════════════════════════════════════════════════════
    path('user/role/', views.get_user_role, name='get-user-role'),
]
