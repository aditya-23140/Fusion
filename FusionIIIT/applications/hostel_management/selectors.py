"""
Hostel Management Selectors

This module contains ALL database queries for the hostel_management app.
NO queries are allowed in views or services.

Query patterns:
- get_*: Returns single object or None
- list_*: Returns QuerySet for lists
- filter_*: Returns QuerySet with specific filters
- count_*: Returns count of objects
"""

from django.db.models import Q, Count, F, Sum
from django.utils import timezone
from datetime import timedelta

from .models import (
    Hall, HallRoom, HallCaretaker, HallWarden,
    HostelLeave, HostelComplaint, RoomAllocation, RoomAllocationChange,
    HostelFine, StaffSchedule, HostelInventory,
    HostelNoticeBoard, GuestRoom, GuestRoomBooking,
    HostelTransactionHistory, HostelStudentAttendance, WorkerReport,
    LeaveStatusChoices, ComplaintStatusChoices, ComplaintPriorityChoices,
    RoomAllocationStatusChoices, FineStatusChoices, BookingStatusChoices
)
from applications.academic_information.models import Student
from applications.globals.models import Staff, Faculty


# ══════════════════════════════════════════════════════════════
# HALL & INFRASTRUCTURE QUERIES
# ══════════════════════════════════════════════════════════════

def get_hall_by_id(hall_id):
    """Get a single hall by hall_id string."""
    return Hall.objects.filter(hall_id=hall_id).first()


def get_all_halls():
    """Get all halls."""
    return Hall.objects.all().order_by('hall_id')


def list_active_halls():
    """Get all active halls."""
    return Hall.objects.filter().order_by('hall_id')


def get_hall_room(hall_id, room_number):
    """Get a specific room in a hall."""
    return HallRoom.objects.filter(
        hall__hall_id=hall_id,
        room_number=room_number
    ).first()


def get_hall_rooms(hall_id):
    """Get all rooms in a hall."""
    return HallRoom.objects.filter(hall__hall_id=hall_id).order_by('block_number', 'room_number')


def list_available_rooms(hall_id):
    """Get available rooms in a hall."""
    return HallRoom.objects.filter(
        hall__hall_id=hall_id,
        status='available'
    ).order_by('block_number', 'room_number')


def list_rooms_by_status(hall_id, status):
    """Get rooms by status in a hall."""
    return HallRoom.objects.filter(
        hall__hall_id=hall_id,
        status=status
    )


def get_hall_caretaker(hall_id):
    """Get active caretaker for a hall."""
    return HallCaretaker.objects.filter(
        hall__hall_id=hall_id,
        is_active=True
    ).first()


def get_hall_warden(hall_id):
    """Get active warden for a hall."""
    return HallWarden.objects.filter(
        hall__hall_id=hall_id,
        is_active=True
    ).first()


def list_hall_caretakers(hall_id):
    """Get all caretakers (active and inactive) for a hall."""
    return HallCaretaker.objects.filter(
        hall__hall_id=hall_id
    ).order_by('-is_active', '-assigned_date')


def list_hall_wardens(hall_id):
    """Get all wardens (active and inactive) for a hall."""
    return HallWarden.objects.filter(
        hall__hall_id=hall_id
    ).order_by('-is_active', '-assigned_date')


# ══════════════════════════════════════════════════════════════
# STUDENT & USER QUERIES
# ══════════════════════════════════════════════════════════════

def get_student(user_id):
    """Get a student by their user ID."""
    return Student.objects.filter(id__user_id=user_id).first()


def get_staff(user_id):
    """Get a staff instance by user ID."""
    return Staff.objects.filter(id__user_id=user_id).first()


def get_faculty(user_id):
    """Get a faculty instance by user ID."""
    return Faculty.objects.filter(id__user_id=user_id).first()


def list_students_by_academic_batch(batch_id):
    """Get all students belonging to a specific academic batch (for bulk allocation)."""
    return Student.objects.filter(
        batch_id=batch_id
    ).select_related(
        'id__user',
        'batch_id__discipline'
    ).order_by('id__user__username')


# ══════════════════════════════════════════════════════════════
# HM-WF-101: LEAVE QUERIES
# ══════════════════════════════════════════════════════════════

def get_student_leave(leave_id):
    """Get a specific leave record."""
    return HostelLeave.objects.filter(id=leave_id).first()


def get_student_current_leave(student_id, start_date, end_date):
    """Check if student has overlapping leave in date range."""
    return HostelLeave.objects.filter(
        student_id=student_id,
        status=LeaveStatusChoices.APPROVED,
        start_date__lt=end_date,
        end_date__gte=start_date
    ).first()


def list_student_leaves(student_id):
    """Get all leaves for a student."""
    return HostelLeave.objects.filter(
        student_id=student_id
    ).order_by('-created_at')


def list_pending_leaves():
    """Get all pending leaves."""
    return HostelLeave.objects.filter(
        status=LeaveStatusChoices.PENDING
    ).order_by('-created_at')


def list_pending_leaves_by_hall(hall_id):
    """Get pending leaves for students in a specific hall."""
    from .models import RoomAllocationStatusChoices
    return HostelLeave.objects.filter(
        status=LeaveStatusChoices.PENDING,
        student__room_allocations__status=RoomAllocationStatusChoices.ALLOCATED
    ).distinct().order_by('-created_at')


def count_student_approved_leaves(student_id, year=None):
    """Count approved leaves for a student in a year."""
    query = HostelLeave.objects.filter(
        student_id=student_id,
        status=LeaveStatusChoices.APPROVED
    )
    if year:
        query = query.filter(start_date__year=year)
    return query.count()


def list_student_leaves_by_status(student_id, status):
    """Get leaves for a student by status."""
    return HostelLeave.objects.filter(
        student_id=student_id,
        status=status
    ).order_by('-created_at')


def list_leaves_requiring_attendance_update(start_date, end_date):
    """Get approved leaves in date range requiring attendance marking."""
    return HostelLeave.objects.filter(
        status=LeaveStatusChoices.APPROVED,
        start_date__lte=end_date,
        end_date__gte=start_date
    )


# ══════════════════════════════════════════════════════════════
# HM-WF-102: COMPLAINT QUERIES
# ══════════════════════════════════════════════════════════════

def get_complaint(complaint_id):
    """Get a specific complaint."""
    return HostelComplaint.objects.filter(id=complaint_id).first()


def list_student_complaints(student_id):
    """Get all complaints from a student."""
    return HostelComplaint.objects.filter(
        student_id=student_id
    ).order_by('-created_at')


def list_open_complaints():
    """Get all open/submitted complaints."""
    return HostelComplaint.objects.filter(
        status=ComplaintStatusChoices.SUBMITTED
    ).order_by('-created_at')


def list_complaints_by_status(status):
    """Get complaints by status."""
    return HostelComplaint.objects.filter(
        status=status
    ).order_by('-created_at')


def list_complaints_by_category(category):
    """Get complaints by category."""
    return HostelComplaint.objects.filter(
        category=category
    ).order_by('-created_at')


def list_complaints_by_hall(hall_id):
    """Get complaints in a specific hall."""
    return HostelComplaint.objects.filter(
        hall__hall_id=hall_id
    ).order_by('-created_at')


def list_complaints_assigned_to_staff(staff_id):
    """Get complaints assigned to a staff member."""
    return HostelComplaint.objects.filter(
        assigned_to_id=staff_id
    ).exclude(status=ComplaintStatusChoices.CLOSED).order_by('-created_at')


def list_escalated_complaints():
    """Get complaints escalated to warden."""
    return HostelComplaint.objects.filter(
        escalated_to_warden=True
    ).order_by('-created_at')


def list_escalated_complaints_for_warden(faculty_id):
    """Get escalated complaints assigned to a warden."""
    return HostelComplaint.objects.filter(
        escalated_to_warden=True,
        escalated_to_id=faculty_id
    ).exclude(status=ComplaintStatusChoices.CLOSED).order_by('-created_at')


def count_open_complaints_for_student(student_id):
    """Count open complaints for a student."""
    return HostelComplaint.objects.filter(
        student_id=student_id,
        status__in=[ComplaintStatusChoices.SUBMITTED, ComplaintStatusChoices.UNDER_REVIEW]
    ).count()


def list_complaints_by_priority(priority):
    """Get complaints by priority level."""
    return HostelComplaint.objects.filter(
        priority=priority
    ).order_by('-created_at')


def list_high_priority_open_complaints():
    """Get high priority and critical open complaints."""
    return HostelComplaint.objects.filter(
        status=ComplaintStatusChoices.SUBMITTED,
        priority__in=[ComplaintPriorityChoices.HIGH, ComplaintPriorityChoices.CRITICAL]
    ).order_by('-created_at')


# ══════════════════════════════════════════════════════════════
# HM-WF-103 & HM-WF-104: ROOM ALLOCATION QUERIES
# ══════════════════════════════════════════════════════════════

def get_student_current_allocation(student):
    """Get student's current active room allocation."""
    return RoomAllocation.objects.filter(
        student=student,
        status=RoomAllocationStatusChoices.ALLOCATED
    ).first()


def get_allocation_by_id(allocation_id):
    """Get a specific room allocation."""
    return RoomAllocation.objects.filter(id=allocation_id).first()


def list_student_allocations(student):
    """Get all room allocations for a student."""
    return RoomAllocation.objects.filter(student=student).order_by('-allocation_date')


def list_allocations_in_room(room_id):
    """Get all allocations in a specific room."""
    return RoomAllocation.objects.filter(
        room_id=room_id
    ).order_by('-allocation_date')


def list_allocations_by_status(status):
    """Get allocations by status."""
    return RoomAllocation.objects.filter(
        status=status
    ).order_by('-allocation_date')


def count_occupied_seats_in_room(room_id):
    """Count occupied seats in a room."""
    return RoomAllocation.objects.filter(
        room_id=room_id,
        status=RoomAllocationStatusChoices.ALLOCATED
    ).count()


def list_unallocated_students():
    """Get students without current room allocation."""
    return Student.objects.exclude(
        room_allocations__status=RoomAllocationStatusChoices.ALLOCATED
    )


def get_all_allocations():
    """Get all room allocations with optimized queries."""
    return RoomAllocation.objects.select_related(
        'student__id__user',
        'room__hall',
        'hall',
        'allocated_by__id__user'
    ).order_by('student_id')


def get_student_allocations(user):
    """Get all room allocations for a student user with optimized queries."""
    student = get_student(user.id)
    if not student:
        return RoomAllocation.objects.none()
    return RoomAllocation.objects.filter(
        student_id=student.pk
    ).select_related(
        'student__id__user',
        'room__hall',
        'hall',
        'allocated_by__id__user'
    ).order_by('student_id')


def get_allocations_by_hall(hall_id):
    """Get all room allocations in a specific hall with optimized queries."""
    return RoomAllocation.objects.filter(
        hall_id=hall_id
    ).select_related(
        'student__id__user',
        'room__hall',
        'hall',
        'allocated_by__id__user'
    ).order_by('student_id')


# ══════════════════════════════════════════════════════════════
# HM-WF-104: ROOM CHANGE QUERIES
# ══════════════════════════════════════════════════════════════

def list_room_changes_by_student(student_id):
    """Get all room change requests for a student."""
    return RoomAllocationChange.objects.filter(
        student_id=student_id
    ).order_by('-requested_date')


def get_room_change(change_id):
    """Get a specific room change request."""
    return RoomAllocationChange.objects.filter(id=change_id).first()


def list_pending_room_changes():
    """Get all pending room change requests."""
    from .models import AllocationChangeStatusChoices
    return RoomAllocationChange.objects.filter(
        status=AllocationChangeStatusChoices.REQUESTED
    ).order_by('-requested_date')


def list_room_changes_by_status(status):
    """Get room changes by status."""
    return RoomAllocationChange.objects.filter(
        status=status
    ).order_by('-requested_date')


def list_room_changes_for_warden(faculty_id):
    """Get room changes pending warden approval."""
    from .models import AllocationChangeStatusChoices
    return RoomAllocationChange.objects.filter(
        status=AllocationChangeStatusChoices.REQUESTED
    ).select_related('student', 'current_room', 'requested_room').order_by('-requested_date')


def list_room_changes_for_caretaker(staff_id):
    """Get room changes pending caretaker approval."""
    from .models import AllocationChangeStatusChoices
    return RoomAllocationChange.objects.filter(
        status=AllocationChangeStatusChoices.APPROVED_WARDEN
    ).select_related('student', 'current_room', 'requested_room').order_by('-requested_date')


def get_all_room_changes():
    """Get all room changes."""
    return RoomAllocationChange.objects.all().order_by('-requested_date')


def get_student_room_changes(user):
    """Get all room changes for a student user."""
    student = get_student(user.id)
    if not student:
        return RoomAllocationChange.objects.none()
    return list_room_changes_by_student(student.pk)


# ══════════════════════════════════════════════════════════════
# HM-WF-105: FINE QUERIES
# ══════════════════════════════════════════════════════════════

def get_fine(fine_id):
    """Get a specific fine record."""
    return HostelFine.objects.filter(id=fine_id).first()


def list_student_fines(student_id):
    """Get all fines for a student."""
    return HostelFine.objects.filter(
        student_id=student_id
    ).order_by('-issued_date')


def list_student_pending_fines(student_id):
    """Get unpaid fines for a student."""
    from .models import FineStatusChoices
    return HostelFine.objects.filter(
        student_id=student_id,
        status=FineStatusChoices.PENDING
    ).order_by('-due_date')


def list_pending_fines():
    """Get all pending fines."""
    from .models import FineStatusChoices
    return HostelFine.objects.filter(
        status=FineStatusChoices.PENDING
    ).order_by('-due_date')


def list_overdue_fines():
    """Get overdue fines (past due date and still pending)."""
    from .models import FineStatusChoices
    return HostelFine.objects.filter(
        status=FineStatusChoices.PENDING,
        due_date__lt=timezone.now().date()
    ).order_by('-due_date')


def list_fines_by_type(fine_type):
    """Get fines by type."""
    return HostelFine.objects.filter(
        fine_type=fine_type
    ).order_by('-issued_date')


def list_fines_by_hall(hall_id):
    """Get all fines issued in a hall."""
    return HostelFine.objects.filter(
        hall__hall_id=hall_id
    ).order_by('-issued_date')


def sum_student_fines(student_id, status=None):
    """Get total fine amount for a student."""
    from .models import FineStatusChoices
    query = HostelFine.objects.filter(student_id=student_id)
    if status:
        query = query.filter(status=status)
    else:
        query = query.exclude(status=FineStatusChoices.CANCELLED)
    result = query.aggregate(total=Sum('amount'))
    return result['total'] or 0


def count_student_unpaid_fines(student_id):
    """Count unpaid fines for a student."""
    from .models import FineStatusChoices
    return HostelFine.objects.filter(
        student_id=student_id,
        status=FineStatusChoices.PENDING
    ).count()


def list_fines_issued_by_staff(staff_id):
    """Get fines issued by a specific staff member."""
    return HostelFine.objects.filter(
        issued_by_id=staff_id
    ).order_by('-issued_date')


# ══════════════════════════════════════════════════════════════
# HM-WF-107: STAFF SCHEDULE QUERIES
# ══════════════════════════════════════════════════════════════

def get_staff_schedule(schedule_id):
    """Get a specific staff schedule."""
    return StaffSchedule.objects.filter(id=schedule_id).first()


def list_hall_schedules(hall_id):
    """Get all schedules for a hall."""
    return StaffSchedule.objects.filter(
        hall__hall_id=hall_id
    ).order_by('day_of_week', 'start_time')


def list_staff_schedules(staff_id):
    """Get all schedules for a staff member."""
    return StaffSchedule.objects.filter(
        staff_id=staff_id
    ).order_by('day_of_week', 'start_time')


def get_staff_schedule_by_day(hall_id, staff_id, day):
    """Get staff schedule for a specific day in a hall."""
    return StaffSchedule.objects.filter(
        hall__hall_id=hall_id,
        staff_id=staff_id,
        day_of_week=day
    ).first()


def list_schedules_by_day(hall_id, day):
    """Get all schedules for a specific day in a hall."""
    return StaffSchedule.objects.filter(
        hall__hall_id=hall_id,
        day_of_week=day
    ).order_by('start_time')


# ══════════════════════════════════════════════════════════════
# HM-WF-108: INVENTORY QUERIES
# ══════════════════════════════════════════════════════════════

def get_inventory_item(inventory_id):
    """Get a specific inventory item."""
    return HostelInventory.objects.filter(id=inventory_id).first()


def list_hall_inventory(hall_id):
    """Get all inventory for a hall."""
    return HostelInventory.objects.filter(
        hall__hall_id=hall_id
    ).order_by('item_name')


def get_inventory_by_name(hall_id, item_name):
    """Get inventory item by name in a hall."""
    return HostelInventory.objects.filter(
        hall__hall_id=hall_id,
        item_name=item_name
    ).first()


def list_low_stock_inventory(hall_id, threshold=5):
    """Get inventory items below threshold."""
    return HostelInventory.objects.filter(
        hall__hall_id=hall_id,
        quantity__lt=threshold
    ).order_by('quantity')


def list_student_fines_by_status(student_id, status):
    """Get student fines filtered by status."""
    return HostelFine.objects.filter(
        student_id=student_id,
        status=status
    ).order_by('-issued_date')


def get_student_complaints_by_status(student_id, statuses):
    """Get student complaints filtered by list of statuses."""
    return HostelComplaint.objects.filter(
        student_id=student_id,
        status__in=statuses
    ).order_by('-created_at')


# ══════════════════════════════════════════════════════════════
# HM-WF-110: NOTICE BOARD QUERIES
# ══════════════════════════════════════════════════════════════

def get_notice(notice_id):
    """Get a specific notice."""
    return HostelNoticeBoard.objects.filter(id=notice_id).first()


def list_active_notices(hall_id):
    """
    Get all active notices for a hall.
    Enforces BR-HM-035: Notice Display Rules (Urgent priority simulation)
    """
    from django.db.models import Case, When, Value, IntegerField
    
    return HostelNoticeBoard.objects.filter(
        hall__hall_id=hall_id,
        is_active=True
    ).annotate(
        priority=Case(
            When(title__icontains='urgent', then=Value(1)),
            When(title__icontains='important', then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        )
    ).order_by('priority', '-posted_date')


def list_all_notices(hall_id):
    """Get all notices (active and archived) for a hall."""
    from django.db.models import Case, When, Value, IntegerField
    
    return HostelNoticeBoard.objects.filter(
        hall__hall_id=hall_id
    ).annotate(
        priority=Case(
            When(title__icontains='urgent', then=Value(1)),
            When(title__icontains='important', then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        )
    ).order_by('priority', '-posted_date')


def list_notices_by_poster(user_id):
    """Get notices posted by a user."""
    return HostelNoticeBoard.objects.filter(
        posted_by_id=user_id
    ).order_by('-posted_date')


# ══════════════════════════════════════════════════════════════
# HM-WF-112: GUEST ROOM QUERIES
# ══════════════════════════════════════════════════════════════

def get_guest_room(room_id):
    """Get a specific guest room."""
    return GuestRoom.objects.filter(id=room_id).first()


def list_hall_guest_rooms(hall_id):
    """Get all guest rooms in a hall."""
    return GuestRoom.objects.filter(
        hall__hall_id=hall_id
    ).order_by('room_number')


def list_available_guest_rooms(hall_id):
    """Get available guest rooms in a hall."""
    return GuestRoom.objects.filter(
        hall__hall_id=hall_id,
        status='available'
    ).order_by('room_number')


def get_guest_booking(booking_id):
    """Get a specific guest room booking."""
    return GuestRoomBooking.objects.filter(id=booking_id).first()


def list_student_guest_bookings(student_id):
    """Get all guest room bookings for a student."""
    return GuestRoomBooking.objects.filter(
        student_id=student_id
    ).order_by('-created_at')


def list_pending_guest_bookings():
    """Get all pending guest room bookings."""
    from .models import GuestRoomBookingStatusChoices
    return GuestRoomBooking.objects.filter(
        status=GuestRoomBookingStatusChoices.PENDING
    ).order_by('-created_at')


def list_guest_bookings_by_status(status):
    """Get guest bookings by status."""
    return GuestRoomBooking.objects.filter(
        status=status
    ).order_by('-created_at')


def list_checked_in_guest_bookings():
    """Get all currently checked-in guest bookings."""
    from .models import GuestRoomBookingStatusChoices
    return GuestRoomBooking.objects.filter(
        status=GuestRoomBookingStatusChoices.CHECKED_IN
    ).order_by('-arrival_date')


def list_upcoming_guest_arrivals(days=7):
    """Get guest bookings arriving within X days."""
    from .models import GuestRoomBookingStatusChoices
    today = timezone.now().date()
    upcoming = today + timedelta(days=days)
    return GuestRoomBooking.objects.filter(
        status=GuestRoomBookingStatusChoices.CONFIRMED,
        arrival_date__range=[today, upcoming]
    ).order_by('arrival_date')


def get_all_guest_bookings():
    """Get all guest room bookings (for staff)."""
    return GuestRoomBooking.objects.all().order_by('-created_at')


def get_student_guest_bookings(user):
    """Get all guest room bookings for a student user."""
    return GuestRoomBooking.objects.filter(
        student_id=user.id
    ).order_by('-created_at')


# ══════════════════════════════════════════════════════════════
# ATTENDANCE & TRANSACTION TRACKING QUERIES
# ══════════════════════════════════════════════════════════════

def get_attendance_record(attendance_id):
    """Get a specific attendance record."""
    return HostelStudentAttendance.objects.filter(id=attendance_id).first()


def list_student_attendance(student_id, days=30):
    """Get attendance records for a student in last X days."""
    start_date = timezone.now().date() - timedelta(days=days)
    return HostelStudentAttendance.objects.filter(
        student_id=student_id,
        date__gte=start_date
    ).order_by('-date')


def list_attendance_by_date(hall_id, date):
    """Get attendance records for a hall on a specific date."""
    return HostelStudentAttendance.objects.filter(
        hall__hall_id=hall_id,
        date=date
    ).order_by('student__user__username')


def list_date_attendance_range(hall_id, start_date, end_date):
    """Get attendance records for a date range."""
    return HostelStudentAttendance.objects.filter(
        hall__hall_id=hall_id,
        date__range=[start_date, end_date]
    ).order_by('-date', 'student__user__username')


def get_transaction_history(transaction_id):
    """Get a specific transaction history record."""
    return HostelTransactionHistory.objects.filter(id=transaction_id).first()


def list_hall_transactions(hall_id):
    """Get transaction history for a hall."""
    return HostelTransactionHistory.objects.filter(
        hall__hall_id=hall_id
    ).order_by('-timestamp')


def list_transactions_by_change_type(hall_id, change_type):
    """Get transactions by change type."""
    return HostelTransactionHistory.objects.filter(
        hall__hall_id=hall_id,
        change_type=change_type
    ).order_by('-timestamp')


# ══════════════════════════════════════════════════════════════
# WORKER REPORT QUERIES
# ══════════════════════════════════════════════════════════════

def get_worker_report(report_id):
    """Get a specific worker report."""
    return WorkerReport.objects.filter(id=report_id).first()


def list_staff_reports(staff_id):
    """Get all reports for a staff member."""
    return WorkerReport.objects.filter(
        worker_id=staff_id
    ).order_by('-year', '-month')


def list_hall_reports(hall_id):
    """Get all reports for a hall."""
    return WorkerReport.objects.filter(
        hall__hall_id=hall_id
    ).order_by('-year', '-month')


def get_monthly_report(staff_id, year, month):
    """Get report for a specific staff member for a specific month."""
    return WorkerReport.objects.filter(
        worker_id=staff_id,
        year=year,
        month=month
    ).first()


# ══════════════════════════════════════════════════════════════
# MISSING SELECTORS REQUIRED BY VIEWS
# ══════════════════════════════════════════════════════════════

def get_all_leaves():
    """Get all leaves with optimized queries (for staff views)."""
    return HostelLeave.objects.select_related(
        'student__id__user',
        'processed_by__id__user'
    ).all().order_by('-created_at')


def get_student_leaves(user):
    """Get all leaves for a student user."""
    student = get_student(user.id)
    if not student:
        return HostelLeave.objects.none()
    return HostelLeave.objects.filter(
        student_id=student.pk
    ).select_related(
        'student__id__user',
        'processed_by__id__user'
    ).order_by('-created_at')


def get_all_complaints():
    """Get all complaints with optimized queries (for staff views)."""
    return HostelComplaint.objects.select_related(
        'student__id__user',
        'assigned_to__id__user',
        'escalated_to__id__user'
    ).all().order_by('-created_at')


def get_student_complaints(user):
    """Get all complaints for a student user."""
    student = get_student(user.id)
    if not student:
        return HostelComplaint.objects.none()
    return HostelComplaint.objects.filter(
        student_id=student.pk
    ).select_related(
        'student__id__user',
        'assigned_to__id__user'
    ).order_by('-created_at')


def get_all_fines():
    """Get all fines with optimized queries (for staff views)."""
    return HostelFine.objects.select_related(
        'student__id__user',
        'issued_by__id__user',
        'waived_by__id__user'
    ).all().order_by('-issued_date')


def get_student_fines(user):
    """Get all fines for a student user."""
    student = get_student(user.id)
    if not student:
        return HostelFine.objects.none()
    return HostelFine.objects.filter(
        student_id=student.pk
    ).select_related(
        'student__id__user',
        'issued_by__id__user',
        'waived_by__id__user'
    ).order_by('-issued_date')


def get_all_schedules():
    """Get all staff schedules with optimized queries."""
    return StaffSchedule.objects.select_related(
        'hall',
        'staff__id__user'
    ).all().order_by('day_of_week', 'start_time')


def get_all_inventory():
    """Get all inventory items with optimized queries."""
    return HostelInventory.objects.select_related(
        'hall'
    ).all().order_by('hall', 'item_name')

# ══════════════════════════════════════════════════════════════
# NEW FEATURE QUERIES (Room Vacation & Extended Stay)
# ══════════════════════════════════════════════════════════════

from .models import RoomVacationRequest, ExtendedStayApplication

def list_room_vacations(filters=None):
    queryset = RoomVacationRequest.objects.select_related('student', 'student__id__user', 'room', 'hall')
    if filters:
        if 'student' in filters:
            queryset = queryset.filter(student=filters['student'])
        if 'hall_id' in filters:
            queryset = queryset.filter(hall_id=filters['hall_id'])
    return queryset.order_by('-created_at')

def get_room_vacation(pk):
    return RoomVacationRequest.objects.filter(pk=pk).first()

def list_extended_stays(filters=None):
    queryset = ExtendedStayApplication.objects.select_related('student', 'student__id__user', 'room', 'hall')
    if filters:
        if 'student' in filters:
            queryset = queryset.filter(student=filters['student'])
        if 'hall_id' in filters:
            queryset = queryset.filter(hall_id=filters['hall_id'])
    return queryset.order_by('-created_at')

def get_extended_stay(pk):
    return ExtendedStayApplication.objects.filter(pk=pk).first()
