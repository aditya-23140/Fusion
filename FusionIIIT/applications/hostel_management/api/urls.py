"""
API URL Configuration for Hostel Management Module

CRITICAL RULES:
- Only router definitions and URL patterns here
- No views, no logic
- Use viewsets with DefaultRouter for RESTful consistency

URL Structure:
/api/hostel-management/
├── halls/                           - Hall management
├── leaves/                          - Leave requests (HM-WF-101)
├── complaints/                      - Complaints (HM-WF-102)
├── room-allocations/               - Room allocation (HM-WF-103)
├── room-changes/                   - Room changes (HM-WF-104)
├── fines/                          - Fine management (HM-WF-105)
├── schedules/                      - Staff schedules (HM-WF-107)
├── inventory/                      - Inventory (HM-WF-108)
├── guest-bookings/                - Guest room bookings (HM-WF-112)
└── notices/                        - Notice board (HM-WF-110)
"""

from django.urls import path, include
from . import views

app_name = 'hostel_management_api'

# ══════════════════════════════════════════════════════════════
# HALL MANAGEMENT ROUTES
# ══════════════════════════════════════════════════════════════
hall_patterns = [
    path('', views.HallListCreateView.as_view(), name='hall-list-create'),
    path('<int:pk>/', views.HallRetrieveUpdateDestroyView.as_view(), name='hall-detail'),
    path('<int:pk>/rooms/', views.HallRoomListCreateView.as_view(), name='hall-rooms-list-create'),
    path('<int:hall_pk>/rooms/<int:pk>/', views.HallRoomRetrieveUpdateDestroyView.as_view(), name='hall-room-detail'),
]

# ══════════════════════════════════════════════════════════════
# SUPER ADMIN MANAGEMENT ROUTES
# ══════════════════════════════════════════════════════════════
admin_patterns = [
    path('assign-warden/', views.WardenAssignmentView.as_view(), name='assign-warden'),
    path('assign-caretaker/', views.CaretakerAssignmentView.as_view(), name='assign-caretaker'),
    path('assignments/', views.StaffAssignmentListView.as_view(), name='assignments-list'),
    path('assignments/<int:pk>/', views.StaffAssignmentDeleteView.as_view(), name='assignments-delete'),
    path('faculty/', views.FacultyListView.as_view(), name='faculty-list'),
    path('staff/', views.StaffListView.as_view(), name='staff-list'),
    path('allocate-batch/', views.BatchAllocationView.as_view(), name='allocate-batch'),
    path('active-batches/', views.ActiveBatchYearsView.as_view(), name='active-batches'),
    path('rooms/<int:pk>/rename/', views.RoomRenameView.as_view(), name='room-rename'),
]

# ══════════════════════════════════════════════════════════════
# LEAVE MANAGEMENT ROUTES (HM-WF-101)
# ══════════════════════════════════════════════════════════════
leave_patterns = [
    path('', views.LeaveListCreateView.as_view(), name='leave-list-create'),
    path('my/', views.LeaveMyListView.as_view(), name='leave-my-list'),
    path('<int:pk>/', views.LeaveRetrieveUpdateView.as_view(), name='leave-detail'),
    path('<int:pk>/approve/', views.LeaveApproveView.as_view(), name='leave-approve'),
    path('<int:pk>/reject/', views.LeaveRejectView.as_view(), name='leave-reject'),
]

# ══════════════════════════════════════════════════════════════
# COMPLAINT MANAGEMENT ROUTES (HM-WF-102)
# ══════════════════════════════════════════════════════════════
complaint_patterns = [
    path('', views.ComplaintListCreateView.as_view(), name='complaint-list-create'),
    path('my/', views.ComplaintMyListView.as_view(), name='complaint-my-list'),
    path('<int:pk>/', views.ComplaintRetrieveUpdateView.as_view(), name='complaint-detail'),
    path('<int:pk>/escalate/', views.ComplaintEscalateView.as_view(), name='complaint-escalate'),
    path('<int:pk>/resolve/', views.ComplaintResolveView.as_view(), name='complaint-resolve'),
]

# ══════════════════════════════════════════════════════════════
# ROOM ALLOCATION ROUTES (HM-WF-103)
# ══════════════════════════════════════════════════════════════
allocation_patterns = [
    path('', views.RoomAllocationListView.as_view(), name='allocation-list'),
    path('<int:pk>/', views.RoomAllocationRetrieveView.as_view(), name='allocation-detail'),
    path('<int:pk>/delete/', views.RoomAllocationDestroyView.as_view(), name='allocation-delete'),
    path('bulk-allocate/', views.BulkRoomAllocationView.as_view(), name='bulk-allocate'),
]

# ══════════════════════════════════════════════════════════════
# ROOM CHANGE ROUTES (HM-WF-104)
# ══════════════════════════════════════════════════════════════
room_change_patterns = [
    path('', views.RoomChangeListCreateView.as_view(), name='room-change-list-create'),
    path('<int:pk>/', views.RoomChangeRetrieveView.as_view(), name='room-change-detail'),
    path('<int:pk>/approve/', views.RoomChangeApproveView.as_view(), name='room-change-approve'),
    path('<int:pk>/reject/', views.RoomChangeRejectView.as_view(), name='room-change-reject'),
]

# ══════════════════════════════════════════════════════════════
# FINE MANAGEMENT ROUTES (HM-WF-105)
# ══════════════════════════════════════════════════════════════
fine_patterns = [
    path('', views.FineListCreateView.as_view(), name='fine-list-create'),
    path('<int:pk>/', views.FineRetrieveView.as_view(), name='fine-detail'),
    path('<int:pk>/mark-paid/', views.FineMarkPaidView.as_view(), name='fine-mark-paid'),
    path('<int:pk>/waive/', views.FineWaiveView.as_view(), name='fine-waive'),
]

# ══════════════════════════════════════════════════════════════
# STAFF SCHEDULE ROUTES (HM-WF-107)
# ══════════════════════════════════════════════════════════════
schedule_patterns = [
    path('', views.StaffScheduleListCreateView.as_view(), name='schedule-list-create'),
    path('<int:pk>/', views.StaffScheduleRetrieveUpdateDestroyView.as_view(), name='schedule-detail'),
]

# ══════════════════════════════════════════════════════════════
# INVENTORY MANAGEMENT ROUTES (HM-WF-108)
# ══════════════════════════════════════════════════════════════
inventory_patterns = [
    path('', views.InventoryListCreateView.as_view(), name='inventory-list-create'),
    path('<int:pk>/', views.InventoryRetrieveUpdateView.as_view(), name='inventory-detail'),
]

# ══════════════════════════════════════════════════════════════
# NOTICE BOARD ROUTES (HM-WF-110)
# ══════════════════════════════════════════════════════════════
notice_patterns = [
    path('', views.NoticeListView.as_view(), name='notice-list'),
    path('<int:pk>/', views.NoticeRetrieveView.as_view(), name='notice-detail'),
]

# ══════════════════════════════════════════════════════════════
# GUEST ROOM BOOKING ROUTES (HM-WF-112)
# ══════════════════════════════════════════════════════════════
guest_booking_patterns = [
    path('', views.GuestBookingListCreateView.as_view(), name='guest-booking-list-create'),
    path('<int:pk>/', views.GuestBookingRetrieveUpdateView.as_view(), name='guest-booking-detail'),
    path('<int:pk>/approve/', views.GuestBookingApproveView.as_view(), name='guest-booking-approve'),
    path('<int:pk>/reject/', views.GuestBookingRejectView.as_view(), name='guest-booking-reject'),
    path('<int:pk>/check-in/', views.GuestBookingCheckInView.as_view(), name='guest-booking-check-in'),
    path('<int:pk>/check-out/', views.GuestBookingCheckOutView.as_view(), name='guest-booking-check-out'),
]

# ══════════════════════════════════════════════════════════════
# ATTENDANCE MANAGEMENT ROUTES
# ══════════════════════════════════════════════════════════════
attendance_patterns = [
    path('hall/<str:hall_id>/', views.AttendanceByHallView.as_view(), name='attendance-by-hall'),
    path('mark/', views.AttendanceMarkView.as_view(), name='attendance-mark'),
]

# ══════════════════════════════════════════════════════════════
# MAIN URL PATTERNS - Namespace organization
# ══════════════════════════════════════════════════════════════
urlpatterns = [
    path('halls/', include((hall_patterns, 'halls'))),
    path('admin/', include((admin_patterns, 'admin'))),
    path('leaves/', include((leave_patterns, 'leaves'))),
    path('complaints/', include((complaint_patterns, 'complaints'))),
    path('room-allocations/', include((allocation_patterns, 'allocations'))),
    path('room-changes/', include((room_change_patterns, 'room-changes'))),
    path('fines/', include((fine_patterns, 'fines'))),
    path('schedules/', include((schedule_patterns, 'schedules'))),
    path('inventory/', include((inventory_patterns, 'inventory'))),
    path('notices/', include((notice_patterns, 'notices'))),
    path('guest-bookings/', include((guest_booking_patterns, 'guest-bookings'))),
    path('attendance/', include((attendance_patterns, 'attendance'))),
]

# ══════════════════════════════════════════════════════════════
# NEW FEATURE ROUTES (Room Vacation & Extended Stay)
# ══════════════════════════════════════════════════════════════
vacation_patterns = [
    path('', views.RoomVacationListCreateView.as_view(), name='vacation-list-create'),
    path('<int:pk>/', views.RoomVacationDetailView.as_view(), name='vacation-detail'),
    path('<int:pk>/verify/', views.RoomVacationVerifyView.as_view(), name='vacation-verify'),
    path('<int:pk>/approve/', views.RoomVacationApproveView.as_view(), name='vacation-approve'),
]

extended_stay_patterns = [
    path('', views.ExtendedStayListCreateView.as_view(), name='extendedstay-list-create'),
    path('<int:pk>/', views.ExtendedStayDetailView.as_view(), name='extendedstay-detail'),
    path('<int:pk>/approve/', views.ExtendedStayApproveView.as_view(), name='extendedstay-approve'),
    path('<int:pk>/reject/', views.ExtendedStayRejectView.as_view(), name='extendedstay-reject'),
]

urlpatterns.extend([
    path('vacations/', include((vacation_patterns, 'vacations'))),
    path('extended-stays/', include((extended_stay_patterns, 'extended-stays'))),
])
