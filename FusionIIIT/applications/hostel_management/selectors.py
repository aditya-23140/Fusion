"""
Selectors - All database read operations for hostel management.

This module contains ALL .objects. queries for the hostel management module.
NO .objects. should appear anywhere else (especially not in views or services for reads).
"""

from django.db.models import Q, Count, F
from django.contrib.auth.models import User
from applications.globals.models import ExtraInfo, Staff, Faculty
from applications.academic_information.models import Student

from .models import (
    Hall,
    HallCaretaker,
    HallWarden,
    GuestRoomBooking,
    StaffSchedule,
    HostelNoticeBoard,
    HostelStudentAttendence,
    HallRoom,
    WorkerReport,
    HostelInventory,
    HostelLeave,
    HostelComplaint,
    HostelAllotment,
    StudentDetails,
    GuestRoom,
    HostelFine,
    HostelTransactionHistory,
    HostelHistory,
    BookingStatus,
    LeaveStatus,
    FineStatus,
)


# ══════════════════════════════════════════════════════════════
# HALL SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_halls():
    """Retrieve all halls ordered by hall_id."""
    return Hall.objects.all().order_by('hall_id')


def get_hall_by_id(hall_id: int):
    """Retrieve a specific hall by its database ID."""
    return Hall.objects.get(id=hall_id)


def get_hall_by_hall_id(hall_id: str):
    """Retrieve a specific hall by its hall_id string."""
    return Hall.objects.get(hall_id=hall_id)


def hall_exists_by_hall_id(hall_id: str) -> bool:
    """Check if a hall exists by hall_id."""
    return Hall.objects.filter(hall_id=hall_id).exists()


# ══════════════════════════════════════════════════════════════
# HALL CARETAKER SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_hall_caretakers():
    """Retrieve all hall caretakers with related data."""
    return HallCaretaker.objects.all().select_related('hall', 'staff__id__user')


def get_caretaker_by_hall(hall):
    """Get caretaker for a specific hall."""
    return HallCaretaker.objects.filter(hall=hall).select_related('staff__id__user').first()


def get_caretaker_by_staff_id(staff_id):
    """Get caretaker assignment by staff ID."""
    return HallCaretaker.objects.filter(staff_id=staff_id).select_related('hall').first()


def get_hall_for_caretaker_user(user: User):
    """Get the hall managed by a caretaker user."""
    try:
        staff_id = user.extrainfo.id
        caretaker = HallCaretaker.objects.filter(staff_id=staff_id).select_related('hall').first()
        return caretaker.hall if caretaker else None
    except:
        return None


# ══════════════════════════════════════════════════════════════
# HALL WARDEN SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_hall_wardens():
    """Retrieve all hall wardens with related data."""
    return HallWarden.objects.all().select_related('hall', 'faculty__id__user')


def get_warden_by_hall(hall):
    """Get warden for a specific hall."""
    return HallWarden.objects.filter(hall=hall).select_related('faculty__id__user').first()


def get_warden_by_faculty_id(faculty_id):
    """Get warden assignment by faculty ID."""
    return HallWarden.objects.filter(faculty_id=faculty_id).select_related('hall').first()


def get_hall_for_warden_user(user: User):
    """Get the hall managed by a warden user."""
    try:
        faculty_id = user.extrainfo.id
        warden = HallWarden.objects.filter(faculty_id=faculty_id).select_related('hall').first()
        return warden.hall if warden else None
    except:
        return None


# ══════════════════════════════════════════════════════════════
# GUEST ROOM BOOKING SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_guest_room_bookings():
    """Retrieve all guest room bookings."""
    return GuestRoomBooking.objects.all().select_related('hall', 'intender').order_by('-booking_date')


def get_booking_by_id(booking_id: int):
    """Retrieve a specific booking by ID."""
    return GuestRoomBooking.objects.select_related('hall', 'intender').get(id=booking_id)


def get_pending_bookings_by_hall(hall):
    """Get all pending guest room bookings for a hall."""
    return GuestRoomBooking.objects.filter(
        hall=hall,
        status=BookingStatus.PENDING
    ).select_related('hall', 'intender')


def get_bookings_by_user(user: User):
    """Get all bookings made by a specific user."""
    return GuestRoomBooking.objects.filter(intender=user).select_related('hall').order_by('-arrival_date')


# ══════════════════════════════════════════════════════════════
# GUEST ROOM SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_guest_rooms():
    """Retrieve all guest rooms."""
    return GuestRoom.objects.all().select_related('hall')


def get_guest_room_by_id(room_id: int):
    """Retrieve a specific guest room by ID."""
    return GuestRoom.objects.select_related('hall').get(id=room_id)


def get_vacant_guest_rooms_by_hall(hall):
    """Get all vacant guest rooms for a specific hall."""
    return GuestRoom.objects.filter(hall=hall, vacant=True).select_related('hall')


def count_vacant_rooms_by_hall_and_type(hall_id: int, room_type: str) -> int:
    """Count vacant rooms of a specific type in a hall."""
    count = GuestRoom.objects.filter(hall_id=hall_id, room_type=room_type, vacant=True).count()
    # Debug: Log the query results
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"Counting vacant rooms: hall_id={hall_id}, room_type={room_type}, count={count}")
    logger.debug(f"All guest rooms for this hall: {GuestRoom.objects.filter(hall_id=hall_id).values('id', 'room_type', 'vacant')}")
    return count


# ══════════════════════════════════════════════════════════════
# STAFF SCHEDULE SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_staff_schedules():
    """Retrieve all staff schedules."""
    return StaffSchedule.objects.all().select_related('hall', 'staff_id__id__user')


def get_staff_schedule_by_hall(hall):
    """Get all staff schedules for a specific hall."""
    return StaffSchedule.objects.filter(hall=hall).select_related('staff_id__id__user')


def get_staff_schedule_by_id(schedule_id: int):
    """Get a specific staff schedule by ID."""
    return StaffSchedule.objects.select_related('hall', 'staff_id__id__user').get(id=schedule_id)


def get_schedule_by_staff_id(staff_id):
    """Get schedule for a specific staff member."""
    return StaffSchedule.objects.filter(staff_id=staff_id).select_related('hall').first()


# ══════════════════════════════════════════════════════════════
# NOTICE BOARD SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_notices():
    """Retrieve all hostel notices, latest first."""
    return HostelNoticeBoard.objects.all().select_related('hall', 'posted_by__user').order_by('-id')


def get_notice_by_id(notice_id: int):
    """Retrieve a specific notice by ID."""
    return HostelNoticeBoard.objects.select_related('hall', 'posted_by__user').get(id=notice_id)


def get_notices_by_hall(hall):
    """Get all notices for a specific hall."""
    return HostelNoticeBoard.objects.filter(hall=hall).select_related('hall', 'posted_by__user').order_by('-id')


# ══════════════════════════════════════════════════════════════
# STUDENT ATTENDANCE SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_attendance():
    """Retrieve all student attendance records."""
    return HostelStudentAttendence.objects.all().select_related('hall', 'student_id__id__user')


def get_attendance_by_hall(hall):
    """Get all attendance records for a specific hall."""
    return HostelStudentAttendence.objects.filter(hall=hall).select_related('student_id__id__user')


def get_attendance_by_student_and_date(student, date):
    """Check if attendance exists for a student on a specific date."""
    return HostelStudentAttendence.objects.filter(student_id=student, date=date).first()


def attendance_exists(student, date) -> bool:
    """Check if attendance record exists."""
    return HostelStudentAttendence.objects.filter(student_id=student, date=date).exists()


# ══════════════════════════════════════════════════════════════
# HALL ROOM SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_hall_rooms():
    """Retrieve all hall rooms."""
    return HallRoom.objects.all().select_related('hall')


def get_rooms_by_hall(hall):
    """Get all rooms for a specific hall."""
    return HallRoom.objects.filter(hall=hall)


def get_room_by_id(room_id: int):
    """Retrieve a specific room by ID."""
    return HallRoom.objects.select_related('hall').get(id=room_id)


def get_available_rooms_by_hall(hall):
    """Get all available rooms (not at full capacity) for a specific hall."""
    return HallRoom.objects.filter(hall=hall).filter(room_cap__gt=F('room_occupied'))


def get_room_by_details(hall, block_no: str, room_no: str):
    """Get a specific room by hall, block and room number."""
    return HallRoom.objects.filter(hall=hall, block_no=block_no, room_no=room_no).first()


def get_allotted_rooms_by_hall(hall):
    """Get all rooms with at least one occupant."""
    return HallRoom.objects.filter(hall=hall, room_occupied__gt=0)


# ══════════════════════════════════════════════════════════════
# WORKER REPORT SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_worker_reports():
    """Retrieve all worker reports."""
    return WorkerReport.objects.all().select_related('hall')


def get_worker_reports_by_hall(hall):
    """Get all worker reports for a specific hall."""
    return WorkerReport.objects.filter(hall=hall)


def get_worker_reports_by_hall_and_period(hall, year: int, month: int):
    """Get worker reports for a specific hall and time period."""
    return WorkerReport.objects.filter(hall=hall, year=year, month=month)


# ══════════════════════════════════════════════════════════════
# HOSTEL INVENTORY SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_inventory():
    """Retrieve all hostel inventory items."""
    return HostelInventory.objects.all().select_related('hall').order_by('inventory_id')


def get_inventory_by_id(inventory_id: int):
    """Retrieve a specific inventory item by ID."""
    return HostelInventory.objects.select_related('hall').get(inventory_id=inventory_id)


def get_inventory_by_hall(hall_id: int):
    """Get all inventory items for a specific hall."""
    return HostelInventory.objects.filter(hall_id=hall_id).order_by('inventory_id')


# ══════════════════════════════════════════════════════════════
# LEAVE SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_leaves():
    """Retrieve all hostel leave applications."""
    return HostelLeave.objects.all().order_by('-start_date')


def get_leave_by_id(leave_id: int):
    """Retrieve a specific leave application by ID."""
    return HostelLeave.objects.get(id=leave_id)


def get_leaves_by_roll_number(roll_num: str):
    """Get all leave applications for a specific student."""
    return HostelLeave.objects.filter(roll_num__iexact=roll_num).order_by('-start_date')


def get_pending_leaves():
    """Get all pending leave applications."""
    return HostelLeave.objects.filter(status=LeaveStatus.PENDING).order_by('-start_date')


# ══════════════════════════════════════════════════════════════
# COMPLAINT SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_complaints():
    """Retrieve all hostel complaints."""
    return HostelComplaint.objects.all()


def get_complaint_by_id(complaint_id: int):
    """Retrieve a specific complaint by ID."""
    return HostelComplaint.objects.get(id=complaint_id)


def get_complaints_by_roll_number(roll_number: str):
    """Get all complaints filed by a specific student."""
    return HostelComplaint.objects.filter(roll_number=roll_number)


# ══════════════════════════════════════════════════════════════
# HOSTEL ALLOTMENT SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_allotments():
    """Retrieve all hostel allotments."""
    return HostelAllotment.objects.all().select_related('hall', 'assignedCaretaker__id__user', 'assignedWarden__id__user')


def get_allotment_by_id(allotment_id: int):
    """Retrieve a specific allotment by ID."""
    return HostelAllotment.objects.select_related('hall', 'assignedCaretaker', 'assignedWarden').get(id=allotment_id)


def get_allotments_by_hall(hall):
    """Get all allotments for a specific hall."""
    return HostelAllotment.objects.filter(hall=hall).select_related('assignedCaretaker', 'assignedWarden')


# ══════════════════════════════════════════════════════════════
# STUDENT DETAILS SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_student_details():
    """Retrieve all student details."""
    return StudentDetails.objects.all()


def get_student_details_by_id(student_id: str):
    """Retrieve student details by ID."""
    return StudentDetails.objects.get(id=student_id)


def get_student_details_by_hall_id(hall_id: str):
    """Get all student details for a specific hall."""
    return StudentDetails.objects.filter(hall_id=hall_id)


# ══════════════════════════════════════════════════════════════
# STUDENT SELECTORS (from globals)
# ══════════════════════════════════════════════════════════════

def get_all_students():
    """Retrieve all students."""
    return Student.objects.all().select_related('id__user')


def get_student_by_id(student_id: str):
    """Retrieve a specific student by ID."""
    return Student.objects.select_related('id__user').get(id=student_id)


def get_students_by_hall_no(hall_no: int):
    """Get all students in a specific hall."""
    return Student.objects.filter(hall_no=hall_no).select_related('id__user')


def student_exists(student_id: str) -> bool:
    """Check if a student exists."""
    return Student.objects.filter(id_id=student_id).exists()


# ══════════════════════════════════════════════════════════════
# HOSTEL FINE SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_fines():
    """Retrieve all hostel fines."""
    return HostelFine.objects.all().select_related('student__id__user', 'hall').order_by('fine_id')


def get_fine_by_id(fine_id: int):
    """Retrieve a specific fine by ID."""
    return HostelFine.objects.select_related('student__id__user', 'hall').get(fine_id=fine_id)


def get_fines_by_hall(hall_id: int):
    """Get all fines for a specific hall."""
    return HostelFine.objects.filter(hall_id=hall_id).select_related('student__id__user').order_by('fine_id')


def get_fines_by_student(student_id: str):
    """Get all fines for a specific student - check both student FK and entered student_id."""
    from django.db.models import Q
    return HostelFine.objects.filter(
        Q(student__id__id=student_id) | Q(student_id_entered=student_id)
    ).select_related('hall').order_by('fine_id')


def get_pending_fines_by_student(student_id: str):
    """Get all pending fines for a specific student."""
    return HostelFine.objects.filter(student_id=student_id, status=FineStatus.PENDING).order_by('fine_id')


# ══════════════════════════════════════════════════════════════
# HISTORY SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_transaction_history():
    """Retrieve all transaction history."""
    return HostelTransactionHistory.objects.all().select_related('hall').order_by('-timestamp')


def get_transaction_history_by_hall(hall):
    """Get transaction history for a specific hall."""
    return HostelTransactionHistory.objects.filter(hall=hall).order_by('-timestamp')


def get_all_hostel_history():
    """Retrieve all hostel history."""
    return HostelHistory.objects.all().select_related('hall', 'caretaker__id__user', 'warden__id__user').order_by('-timestamp')


def get_hostel_history_by_hall(hall):
    """Get hostel history for a specific hall."""
    return HostelHistory.objects.filter(hall=hall).select_related('caretaker__id__user', 'warden__id__user').order_by('-timestamp')


# ══════════════════════════════════════════════════════════════
# STAFF & FACULTY SELECTORS (from globals)
# ══════════════════════════════════════════════════════════════

def get_all_staff():
    """Retrieve all staff members."""
    return Staff.objects.all().select_related('id__user')


def get_staff_by_id(staff_id):
    """Retrieve a specific staff member by ID."""
    return Staff.objects.select_related('id__user').get(pk=staff_id)


def get_staff_by_username(username: str):
    """Get staff member by username."""
    return Staff.objects.select_related('id__user').get(id__user__username=username)


def get_all_faculty():
    """Retrieve all faculty members."""
    return Faculty.objects.all().select_related('id__user')


def get_faculty_by_id(faculty_id):
    """Retrieve a specific faculty member by ID."""
    return Faculty.objects.select_related('id__user').get(pk=faculty_id)


def get_faculty_by_username(username: str):
    """Get faculty member by username."""
    return Faculty.objects.select_related('id__user').get(id__user__username=username)


# ══════════════════════════════════════════════════════════════
# USER SELECTORS
# ══════════════════════════════════════════════════════════════

def get_user_by_username(username: str):
    """Get user by username."""
    return User.objects.get(username=username)


def user_exists_by_username(username: str) -> bool:
    """Check if user exists by username."""
    return User.objects.filter(username=username).exists()


# ══════════════════════════════════════════════════════════════
# USER ROLE SELECTORS
# ══════════════════════════════════════════════════════════════

def get_user_hostel_role(user: User):
    """
    Determine the hostel role for a user.
    Returns: 'caretaker', 'warden', 'student', or None
    """
    try:
        extra_info = user.extrainfo
        
        # Check if user is a caretaker
        if extra_info.user_type == 'staff':
            caretaker = HallCaretaker.objects.filter(staff__id=extra_info).select_related('hall').first()
            if caretaker:
                return {
                    'role': 'caretaker',
                    'hall': caretaker.hall.hall_id if caretaker.hall else None,
                    'hall_name': caretaker.hall.hall_name if caretaker.hall else None
                }
        
        # Check if user is a warden
        if extra_info.user_type == 'faculty':
            warden = HallWarden.objects.filter(faculty__id=extra_info).select_related('hall').first()
            if warden:
                return {
                    'role': 'warden',
                    'hall': warden.hall.hall_id if warden.hall else None,
                    'hall_name': warden.hall.hall_name if warden.hall else None
                }
        
        # Check if user is a student
        if extra_info.user_type == 'student':
            return {
                'role': 'student',
                'hall': None,
                'hall_name': None
            }
        
        return None
    except Exception:
        return None


def is_user_caretaker(user: User) -> bool:
    """Check if user is a hostel caretaker."""
    role_info = get_user_hostel_role(user)
    return role_info is not None and role_info.get('role') == 'caretaker'


def is_user_warden(user: User) -> bool:
    """Check if user is a hostel warden."""
    role_info = get_user_hostel_role(user)
    return role_info is not None and role_info.get('role') == 'warden'


def is_user_student(user: User) -> bool:
    """Check if user is a student."""
    role_info = get_user_hostel_role(user)
    return role_info is not None and role_info.get('role') == 'student'
"""
Selectors - All database read operations for hostel management.

This module contains ALL .objects. queries for the hostel management module.
NO .objects. should appear anywhere else (especially not in views or services for reads).
"""

from django.db.models import Q, Count, F
from django.contrib.auth.models import User
from applications.globals.models import ExtraInfo, Staff, Faculty
from applications.academic_information.models import Student

from .models import (
    Hall,
    HallCaretaker,
    HallWarden,
    GuestRoomBooking,
    StaffSchedule,
    HostelNoticeBoard,
    HostelStudentAttendence,
    HallRoom,
    WorkerReport,
    HostelInventory,
    HostelLeave,
    HostelComplaint,
    HostelAllotment,
    StudentDetails,
    GuestRoom,
    HostelFine,
    HostelTransactionHistory,
    HostelHistory,
    BookingStatus,
    LeaveStatus,
    FineStatus,
)


# ══════════════════════════════════════════════════════════════
# HALL SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_halls():
    """Retrieve all halls ordered by hall_id."""
    return Hall.objects.all().order_by('hall_id')


def get_hall_by_id(hall_id: int):
    """Retrieve a specific hall by its database ID."""
    return Hall.objects.get(id=hall_id)


def get_hall_by_hall_id(hall_id: str):
    """Retrieve a specific hall by its hall_id string."""
    return Hall.objects.get(hall_id=hall_id)


def hall_exists_by_hall_id(hall_id: str) -> bool:
    """Check if a hall exists by hall_id."""
    return Hall.objects.filter(hall_id=hall_id).exists()


# ══════════════════════════════════════════════════════════════
# HALL CARETAKER SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_hall_caretakers():
    """Retrieve all hall caretakers with related data."""
    return HallCaretaker.objects.all().select_related('hall', 'staff__id__user')


def get_caretaker_by_hall(hall):
    """Get caretaker for a specific hall."""
    return HallCaretaker.objects.filter(hall=hall).select_related('staff__id__user').first()


def get_caretaker_by_staff_id(staff_id):
    """Get caretaker assignment by staff ID."""
    return HallCaretaker.objects.filter(staff_id=staff_id).select_related('hall').first()


def get_hall_for_caretaker_user(user: User):
    """Get the hall managed by a caretaker user."""
    try:
        staff_id = user.extrainfo.id
        caretaker = HallCaretaker.objects.filter(staff_id=staff_id).select_related('hall').first()
        return caretaker.hall if caretaker else None
    except:
        return None


# ══════════════════════════════════════════════════════════════
# HALL WARDEN SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_hall_wardens():
    """Retrieve all hall wardens with related data."""
    return HallWarden.objects.all().select_related('hall', 'faculty__id__user')


def get_warden_by_hall(hall):
    """Get warden for a specific hall."""
    return HallWarden.objects.filter(hall=hall).select_related('faculty__id__user').first()


def get_warden_by_faculty_id(faculty_id):
    """Get warden assignment by faculty ID."""
    return HallWarden.objects.filter(faculty_id=faculty_id).select_related('hall').first()


def get_hall_for_warden_user(user: User):
    """Get the hall managed by a warden user."""
    try:
        faculty_id = user.extrainfo.id
        warden = HallWarden.objects.filter(faculty_id=faculty_id).select_related('hall').first()
        return warden.hall if warden else None
    except:
        return None


# ══════════════════════════════════════════════════════════════
# GUEST ROOM BOOKING SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_guest_room_bookings():
    """Retrieve all guest room bookings."""
    return GuestRoomBooking.objects.all().select_related('hall', 'intender').order_by('-booking_date')


def get_booking_by_id(booking_id: int):
    """Retrieve a specific booking by ID."""
    return GuestRoomBooking.objects.select_related('hall', 'intender').get(id=booking_id)


def get_pending_bookings_by_hall(hall):
    """Get all pending guest room bookings for a hall."""
    return GuestRoomBooking.objects.filter(
        hall=hall,
        status=BookingStatus.PENDING
    ).select_related('hall', 'intender')


def get_bookings_by_user(user: User):
    """Get all bookings made by a specific user."""
    return GuestRoomBooking.objects.filter(intender=user).select_related('hall').order_by('-arrival_date')


# ══════════════════════════════════════════════════════════════
# GUEST ROOM SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_guest_rooms():
    """Retrieve all guest rooms."""
    return GuestRoom.objects.all().select_related('hall')


def get_guest_room_by_id(room_id: int):
    """Retrieve a specific guest room by ID."""
    return GuestRoom.objects.select_related('hall').get(id=room_id)


def get_vacant_guest_rooms_by_hall(hall):
    """Get all vacant guest rooms for a specific hall."""
    return GuestRoom.objects.filter(hall=hall, vacant=True).select_related('hall')


def count_vacant_rooms_by_hall_and_type(hall_id: int, room_type: str) -> int:
    """Count vacant rooms of a specific type in a hall."""
    count = GuestRoom.objects.filter(hall_id=hall_id, room_type=room_type, vacant=True).count()
    # Debug: Log the query results
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"Counting vacant rooms: hall_id={hall_id}, room_type={room_type}, count={count}")
    logger.debug(f"All guest rooms for this hall: {GuestRoom.objects.filter(hall_id=hall_id).values('id', 'room_type', 'vacant')}")
    return count


# ══════════════════════════════════════════════════════════════
# STAFF SCHEDULE SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_staff_schedules():
    """Retrieve all staff schedules."""
    return StaffSchedule.objects.all().select_related('hall', 'staff_id__id__user')


def get_staff_schedule_by_hall(hall):
    """Get all staff schedules for a specific hall."""
    return StaffSchedule.objects.filter(hall=hall).select_related('staff_id__id__user')


def get_staff_schedule_by_id(schedule_id: int):
    """Get a specific staff schedule by ID."""
    return StaffSchedule.objects.select_related('hall', 'staff_id__id__user').get(id=schedule_id)


def get_schedule_by_staff_id(staff_id):
    """Get schedule for a specific staff member."""
    return StaffSchedule.objects.filter(staff_id=staff_id).select_related('hall').first()


# ══════════════════════════════════════════════════════════════
# NOTICE BOARD SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_notices():
    """Retrieve all hostel notices, latest first."""
    return HostelNoticeBoard.objects.all().select_related('hall', 'posted_by__user').order_by('-id')


def get_notice_by_id(notice_id: int):
    """Retrieve a specific notice by ID."""
    return HostelNoticeBoard.objects.select_related('hall', 'posted_by__user').get(id=notice_id)


def get_notices_by_hall(hall):
    """Get all notices for a specific hall."""
    return HostelNoticeBoard.objects.filter(hall=hall).select_related('hall', 'posted_by__user').order_by('-id')


# ══════════════════════════════════════════════════════════════
# STUDENT ATTENDANCE SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_attendance():
    """Retrieve all student attendance records."""
    return HostelStudentAttendence.objects.all().select_related('hall', 'student_id__id__user')


def get_attendance_by_hall(hall):
    """Get all attendance records for a specific hall."""
    return HostelStudentAttendence.objects.filter(hall=hall).select_related('student_id__id__user')


def get_attendance_by_student_and_date(student, date):
    """Check if attendance exists for a student on a specific date."""
    return HostelStudentAttendence.objects.filter(student_id=student, date=date).first()


def attendance_exists(student, date) -> bool:
    """Check if attendance record exists."""
    return HostelStudentAttendence.objects.filter(student_id=student, date=date).exists()


# ══════════════════════════════════════════════════════════════
# HALL ROOM SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_hall_rooms():
    """Retrieve all hall rooms."""
    return HallRoom.objects.all().select_related('hall')


def get_rooms_by_hall(hall):
    """Get all rooms for a specific hall."""
    return HallRoom.objects.filter(hall=hall)


def get_room_by_id(room_id: int):
    """Retrieve a specific room by ID."""
    return HallRoom.objects.select_related('hall').get(id=room_id)


def get_available_rooms_by_hall(hall):
    """Get all available rooms (not at full capacity) for a specific hall."""
    return HallRoom.objects.filter(hall=hall).filter(room_cap__gt=F('room_occupied'))


def get_room_by_details(hall, block_no: str, room_no: str):
    """Get a specific room by hall, block and room number."""
    return HallRoom.objects.filter(hall=hall, block_no=block_no, room_no=room_no).first()


def get_allotted_rooms_by_hall(hall):
    """Get all rooms with at least one occupant."""
    return HallRoom.objects.filter(hall=hall, room_occupied__gt=0)


# ══════════════════════════════════════════════════════════════
# WORKER REPORT SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_worker_reports():
    """Retrieve all worker reports."""
    return WorkerReport.objects.all().select_related('hall')


def get_worker_reports_by_hall(hall):
    """Get all worker reports for a specific hall."""
    return WorkerReport.objects.filter(hall=hall)


def get_worker_reports_by_hall_and_period(hall, year: int, month: int):
    """Get worker reports for a specific hall and time period."""
    return WorkerReport.objects.filter(hall=hall, year=year, month=month)


# ══════════════════════════════════════════════════════════════
# HOSTEL INVENTORY SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_inventory():
    """Retrieve all hostel inventory items."""
    return HostelInventory.objects.all().select_related('hall').order_by('inventory_id')


def get_inventory_by_id(inventory_id: int):
    """Retrieve a specific inventory item by ID."""
    return HostelInventory.objects.select_related('hall').get(inventory_id=inventory_id)


def get_inventory_by_hall(hall_id: int):
    """Get all inventory items for a specific hall."""
    return HostelInventory.objects.filter(hall_id=hall_id).order_by('inventory_id')


# ══════════════════════════════════════════════════════════════
# LEAVE SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_leaves():
    """Retrieve all hostel leave applications."""
    return HostelLeave.objects.all().order_by('-start_date')


def get_leave_by_id(leave_id: int):
    """Retrieve a specific leave application by ID."""
    return HostelLeave.objects.get(id=leave_id)


def get_leaves_by_roll_number(roll_num: str):
    """Get all leave applications for a specific student."""
    return HostelLeave.objects.filter(roll_num__iexact=roll_num).order_by('-start_date')


def get_pending_leaves():
    """Get all pending leave applications."""
    return HostelLeave.objects.filter(status=LeaveStatus.PENDING).order_by('-start_date')


# ══════════════════════════════════════════════════════════════
# COMPLAINT SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_complaints():
    """Retrieve all hostel complaints."""
    return HostelComplaint.objects.all()


def get_complaint_by_id(complaint_id: int):
    """Retrieve a specific complaint by ID."""
    return HostelComplaint.objects.get(id=complaint_id)


def get_complaints_by_roll_number(roll_number: str):
    """Get all complaints filed by a specific student."""
    return HostelComplaint.objects.filter(roll_number=roll_number)


# ══════════════════════════════════════════════════════════════
# HOSTEL ALLOTMENT SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_allotments():
    """Retrieve all hostel allotments."""
    return HostelAllotment.objects.all().select_related('hall', 'assignedCaretaker__id__user', 'assignedWarden__id__user')


def get_allotment_by_id(allotment_id: int):
    """Retrieve a specific allotment by ID."""
    return HostelAllotment.objects.select_related('hall', 'assignedCaretaker', 'assignedWarden').get(id=allotment_id)


def get_allotments_by_hall(hall):
    """Get all allotments for a specific hall."""
    return HostelAllotment.objects.filter(hall=hall).select_related('assignedCaretaker', 'assignedWarden')


# ══════════════════════════════════════════════════════════════
# STUDENT DETAILS SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_student_details():
    """Retrieve all student details."""
    return StudentDetails.objects.all()


def get_student_details_by_id(student_id: str):
    """Retrieve student details by ID."""
    return StudentDetails.objects.get(id=student_id)


def get_student_details_by_hall_id(hall_id: str):
    """Get all student details for a specific hall."""
    return StudentDetails.objects.filter(hall_id=hall_id)


# ══════════════════════════════════════════════════════════════
# STUDENT SELECTORS (from globals)
# ══════════════════════════════════════════════════════════════

def get_all_students():
    """Retrieve all students."""
    return Student.objects.all().select_related('id__user')


def get_student_by_id(student_id: str):
    """Retrieve a specific student by ID."""
    return Student.objects.select_related('id__user').get(id=student_id)


def get_students_by_hall_no(hall_no: int):
    """Get all students in a specific hall."""
    return Student.objects.filter(hall_no=hall_no).select_related('id__user')


def student_exists(student_id: str) -> bool:
    """Check if a student exists."""
    return Student.objects.filter(id_id=student_id).exists()


# ══════════════════════════════════════════════════════════════
# HOSTEL FINE SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_fines():
    """Retrieve all hostel fines."""
    return HostelFine.objects.all().select_related('student__id__user', 'hall').order_by('fine_id')


def get_fine_by_id(fine_id: int):
    """Retrieve a specific fine by ID."""
    return HostelFine.objects.select_related('student__id__user', 'hall').get(fine_id=fine_id)


def get_fines_by_hall(hall_id: int):
    """Get all fines for a specific hall."""
    return HostelFine.objects.filter(hall_id=hall_id).select_related('student__id__user').order_by('fine_id')


def get_fines_by_student(student_id: str):
    """Get all fines for a specific student."""
    return HostelFine.objects.filter(student_id=student_id).select_related('hall').order_by('fine_id')


def get_pending_fines_by_student(student_id: str):
    """Get all pending fines for a specific student."""
    return HostelFine.objects.filter(student_id=student_id, status=FineStatus.PENDING).order_by('fine_id')


# ══════════════════════════════════════════════════════════════
# HISTORY SELECTORS
# ══════════════════════════════════════════════════════════════

def get_all_transaction_history():
    """Retrieve all transaction history."""
    return HostelTransactionHistory.objects.all().select_related('hall').order_by('-timestamp')


def get_transaction_history_by_hall(hall):
    """Get transaction history for a specific hall."""
    return HostelTransactionHistory.objects.filter(hall=hall).order_by('-timestamp')


def get_all_hostel_history():
    """Retrieve all hostel history."""
    return HostelHistory.objects.all().select_related('hall', 'caretaker__id__user', 'warden__id__user').order_by('-timestamp')


def get_hostel_history_by_hall(hall):
    """Get hostel history for a specific hall."""
    return HostelHistory.objects.filter(hall=hall).select_related('caretaker__id__user', 'warden__id__user').order_by('-timestamp')


# ══════════════════════════════════════════════════════════════
# STAFF & FACULTY SELECTORS (from globals)
# ══════════════════════════════════════════════════════════════

def get_all_staff():
    """Retrieve all staff members."""
    return Staff.objects.all().select_related('id__user')


def get_staff_by_id(staff_id):
    """Retrieve a specific staff member by ID."""
    return Staff.objects.select_related('id__user').get(pk=staff_id)


def get_staff_by_username(username: str):
    """Get staff member by username."""
    return Staff.objects.select_related('id__user').get(id__user__username=username)


def get_all_faculty():
    """Retrieve all faculty members."""
    return Faculty.objects.all().select_related('id__user')


def get_faculty_by_id(faculty_id):
    """Retrieve a specific faculty member by ID."""
    return Faculty.objects.select_related('id__user').get(pk=faculty_id)


def get_faculty_by_username(username: str):
    """Get faculty member by username."""
    return Faculty.objects.select_related('id__user').get(id__user__username=username)


# ══════════════════════════════════════════════════════════════
# USER SELECTORS
# ══════════════════════════════════════════════════════════════

def get_user_by_username(username: str):
    """Get user by username."""
    return User.objects.get(username=username)


def user_exists_by_username(username: str) -> bool:
    """Check if user exists by username."""
    return User.objects.filter(username=username).exists()


# ══════════════════════════════════════════════════════════════
# USER ROLE SELECTORS
# ══════════════════════════════════════════════════════════════

def get_user_hostel_role(user: User):
    """
    Determine the hostel role for a user.
    Returns: 'caretaker', 'warden', 'student', or None
    """
    try:
        extra_info = user.extrainfo
        
        # Check if user is a caretaker
        if extra_info.user_type == 'staff':
            caretaker = HallCaretaker.objects.filter(staff__id=extra_info).select_related('hall').first()
            if caretaker:
                return {
                    'role': 'caretaker',
                    'hall': caretaker.hall.hall_id if caretaker.hall else None,
                    'hall_name': caretaker.hall.hall_name if caretaker.hall else None
                }
        
        # Check if user is a warden
        if extra_info.user_type == 'faculty':
            warden = HallWarden.objects.filter(faculty__id=extra_info).select_related('hall').first()
            if warden:
                return {
                    'role': 'warden',
                    'hall': warden.hall.hall_id if warden.hall else None,
                    'hall_name': warden.hall.hall_name if warden.hall else None
                }
        
        # Check if user is a student
        if extra_info.user_type == 'student':
            return {
                'role': 'student',
                'hall': None,
                'hall_name': None
            }
        
        return None
    except Exception:
        return None


def is_user_caretaker(user: User) -> bool:
    """Check if user is a hostel caretaker."""
    role_info = get_user_hostel_role(user)
    return role_info is not None and role_info.get('role') == 'caretaker'


def is_user_warden(user: User) -> bool:
    """Check if user is a hostel warden."""
    role_info = get_user_hostel_role(user)
    return role_info is not None and role_info.get('role') == 'warden'


def is_user_student(user: User) -> bool:
    """Check if user is a student."""
    role_info = get_user_hostel_role(user)
    return role_info is not None and role_info.get('role') == 'student'
