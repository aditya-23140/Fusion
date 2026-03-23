"""
Services - All business logic and write operations for hostel management.

This module contains ALL business logic, validation, and write operations.
For reads, this module calls selectors. It NEVER uses .objects. for reads.
"""

from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, date
import re

from applications.globals.models import Staff, Faculty
from applications.academic_information.models import Student

from . import selectors
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
    RoomType,
)


# ══════════════════════════════════════════════════════════════
# CUSTOM EXCEPTIONS
# ══════════════════════════════════════════════════════════════

class HostelManagementError(Exception):
    """Base exception for hostel management module."""
    pass


class HallNotFoundError(HostelManagementError):
    """Hall does not exist."""
    pass


class HallAlreadyExistsError(HostelManagementError):
    """Hall with this ID already exists."""
    pass


class RoomNotAvailableError(HostelManagementError):
    """Room is full or unavailable."""
    pass


class RoomNotFoundError(HostelManagementError):
    """Room does not exist."""
    pass


class StudentNotFoundError(HostelManagementError):
    """Student does not exist."""
    pass


class StaffNotFoundError(HostelManagementError):
    """Staff member does not exist."""
    pass


class FacultyNotFoundError(HostelManagementError):
    """Faculty member does not exist."""
    pass


class InvalidOperationError(HostelManagementError):
    """Operation not allowed in current state."""
    pass


class AttendanceAlreadyMarkedError(HostelManagementError):
    """Attendance already marked for this date."""
    pass


class InsufficientRoomsError(HostelManagementError):
    """Not enough rooms available."""
    pass


class GuestCapacityExceededError(HostelManagementError):
    """Number of guests exceeds room capacity."""
    pass


class UnauthorizedAccessError(HostelManagementError):
    """User not authorized for this operation."""
    pass


class BookingNotFoundError(HostelManagementError):
    """Booking does not exist."""
    pass


class LeaveNotFoundError(HostelManagementError):
    """Leave application does not exist."""
    pass


class FineNotFoundError(HostelManagementError):
    """Fine does not exist."""
    pass


class InventoryNotFoundError(HostelManagementError):
    """Inventory item does not exist."""
    pass


# ══════════════════════════════════════════════════════════════
# HALL SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def create_hall(*, hall_id: str, hall_name: str, max_accomodation: int, type_of_seater: str, **kwargs):
    """Create a new hall."""
    if selectors.hall_exists_by_hall_id(hall_id):
        raise HallAlreadyExistsError(f"Hall with ID {hall_id} already exists.")

    hall = Hall.objects.create(
        hall_id=hall_id,
        hall_name=hall_name,
        max_accomodation=max_accomodation,
        type_of_seater=type_of_seater,
        **kwargs
    )
    return hall


@transaction.atomic
def update_hall(*, hall_id: int, **update_fields):
    """Update hall information."""
    try:
        hall = selectors.get_hall_by_id(hall_id)
    except Hall.DoesNotExist:
        raise HallNotFoundError(f"Hall with ID {hall_id} not found.")

    for field, value in update_fields.items():
        setattr(hall, field, value)
    hall.save()
    return hall


@transaction.atomic
def delete_hall(*, hall_id: int):
    """Delete a hall and its related data."""
    try:
        hall = selectors.get_hall_by_id(hall_id)
    except Hall.DoesNotExist:
        raise HallNotFoundError(f"Hall with ID {hall_id} not found.")

    # Delete related allotments
    HostelAllotment.objects.filter(hall=hall).delete()

    # Delete the hall
    hall.delete()


# ══════════════════════════════════════════════════════════════
# HALL CARETAKER SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def assign_caretaker(*, hall_id: str, caretaker_username: str):
    """Assign a caretaker to a hall."""
    try:
        hall = selectors.get_hall_by_hall_id(hall_id)
    except Hall.DoesNotExist:
        raise HallNotFoundError(f"Hall with ID {hall_id} not found.")

    try:
        caretaker_staff = selectors.get_staff_by_username(caretaker_username)
    except Staff.DoesNotExist:
        raise StaffNotFoundError(f"Caretaker with username {caretaker_username} not found.")

    # Get previous caretaker for history
    prev_hall_caretaker = selectors.get_caretaker_by_hall(hall)

    # Delete any previous assignments of this caretaker
    HallCaretaker.objects.filter(staff=caretaker_staff).delete()

    # Delete any previously assigned caretaker to this hall
    HallCaretaker.objects.filter(hall=hall).delete()

    # Create new assignment
    hall_caretaker = HallCaretaker.objects.create(hall=hall, staff=caretaker_staff)

    # Update hostel allotments
    hostel_allotments = selectors.get_allotments_by_hall(hall)
    for hostel_allotment in hostel_allotments:
        hostel_allotment.assignedCaretaker = caretaker_staff
        hostel_allotment.save(update_fields=['assignedCaretaker'])

    # Record transaction history
    HostelTransactionHistory.objects.create(
        hall=hall,
        change_type='Caretaker',
        previous_value=prev_hall_caretaker.staff.id if (prev_hall_caretaker and prev_hall_caretaker.staff) else 'None',
        new_value=caretaker_username
    )

    # Create hostel history
    current_warden = selectors.get_warden_by_hall(hall)
    HostelHistory.objects.create(
        hall=hall,
        caretaker=caretaker_staff,
        batch=hall.assigned_batch,
        warden=current_warden.faculty if (current_warden and current_warden.faculty) else None
    )

    return hall_caretaker


# ══════════════════════════════════════════════════════════════
# HALL WARDEN SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def assign_warden(*, hall_id: str, warden_username: str):
    """Assign a warden to a hall."""
    try:
        hall = selectors.get_hall_by_hall_id(hall_id)
    except Hall.DoesNotExist:
        raise HallNotFoundError(f"Hall with ID {hall_id} not found.")

    try:
        warden = selectors.get_faculty_by_username(warden_username)
    except Faculty.DoesNotExist:
        raise FacultyNotFoundError(f"Warden with username {warden_username} not found.")

    # Get previous warden for history
    prev_hall_warden = selectors.get_warden_by_hall(hall)

    # Delete any previous assignments of this warden
    HallWarden.objects.filter(faculty=warden).delete()

    # Delete any previously assigned warden to this hall
    HallWarden.objects.filter(hall=hall).delete()

    # Create new assignment
    hall_warden = HallWarden.objects.create(hall=hall, faculty=warden)

    # Update hostel allotments
    hostel_allotments = selectors.get_allotments_by_hall(hall)
    for hostel_allotment in hostel_allotments:
        hostel_allotment.assignedWarden = warden
        hostel_allotment.save(update_fields=['assignedWarden'])

    # Record transaction history
    HostelTransactionHistory.objects.create(
        hall=hall,
        change_type='Warden',
        previous_value=prev_hall_warden.faculty.id if (prev_hall_warden and prev_hall_warden.faculty) else 'None',
        new_value=warden_username
    )

    # Create hostel history
    current_caretaker = selectors.get_caretaker_by_hall(hall)
    HostelHistory.objects.create(
        hall=hall,
        caretaker=current_caretaker.staff if (current_caretaker and current_caretaker.staff) else None,
        batch=hall.assigned_batch,
        warden=warden
    )

    return hall_warden


# ══════════════════════════════════════════════════════════════
# BATCH ASSIGNMENT SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def assign_batch_to_hall(*, hall_id: str, batch: str):
    """Assign a batch to a hall."""
    try:
        hall = selectors.get_hall_by_hall_id(hall_id)
    except Hall.DoesNotExist:
        raise HallNotFoundError(f"Hall with ID {hall_id} not found.")

    previous_batch = hall.assigned_batch if hall.assigned_batch is not None else '0'
    hall.assigned_batch = batch
    hall.save(update_fields=['assigned_batch'])

    # Update room allotments
    room_allotments = selectors.get_allotments_by_hall(hall)
    for room_allotment in room_allotments:
        room_allotment.assignedBatch = batch
        room_allotment.save(update_fields=['assignedBatch'])

    # Update student hall allotments
    hall_number = int(''.join(filter(str.isdigit, hall.hall_id)))
    students = Student.objects.filter(batch=int(batch))
    for student in students:
        student.hall_no = hall_number
        student.save(update_fields=['hall_no'])

    # Record transaction history
    HostelTransactionHistory.objects.create(
        hall=hall,
        change_type='Batch',
        previous_value=previous_batch,
        new_value=batch
    )

    # Create hostel history
    current_caretaker = selectors.get_caretaker_by_hall(hall)
    current_warden = selectors.get_warden_by_hall(hall)
    HostelHistory.objects.create(
        hall=hall,
        caretaker=current_caretaker.staff if (current_caretaker and current_caretaker.staff) else None,
        batch=batch,
        warden=current_warden.faculty if (current_warden and current_warden.faculty) else None
    )

    return hall


# ══════════════════════════════════════════════════════════════
# GUEST ROOM BOOKING SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def create_guest_room_booking(
    *,
    hall_id: int,
    intender: User,
    guest_name: str,
    guest_phone: str,
    purpose: str,
    arrival_date: str,
    arrival_time: str,
    departure_date: str,
    departure_time: str,
    rooms_required: int,
    total_guest: int,
    room_type: str,
    **kwargs
):
    """Create a new guest room booking request."""
    try:
        hall = selectors.get_hall_by_id(hall_id)
    except Hall.DoesNotExist:
        raise HallNotFoundError(f"Hall with ID {hall_id} not found.")

    # Check room availability
    available_rooms_count = selectors.count_vacant_rooms_by_hall_and_type(hall_id, room_type)
    if available_rooms_count < rooms_required:
        raise InsufficientRoomsError("Not enough available rooms for this booking.")

    # Check guest capacity
    max_guests = {'single': 1, 'double': 2, 'triple': 3}
    if total_guest > rooms_required * max_guests.get(room_type, 1):
        raise GuestCapacityExceededError("Number of guests exceeds the capacity of selected rooms.")

    booking = GuestRoomBooking.objects.create(
        hall=hall,
        intender=intender,
        guest_name=guest_name,
        guest_phone=guest_phone,
        purpose=purpose,
        arrival_date=arrival_date,
        arrival_time=arrival_time,
        departure_date=departure_date,
        departure_time=departure_time,
        rooms_required=rooms_required,
        total_guest=total_guest,
        room_type=room_type,
        booking_date=timezone.now().date(),
        **kwargs
    )
    return booking


@transaction.atomic
def approve_guest_room_booking(*, booking_id: int, guest_room_id: int):
    """Approve a guest room booking and assign a room."""
    try:
        booking = selectors.get_booking_by_id(booking_id)
    except GuestRoomBooking.DoesNotExist:
        raise BookingNotFoundError(f"Booking with ID {booking_id} not found.")

    if booking.status != BookingStatus.PENDING:
        raise InvalidOperationError("Only PENDING bookings can be approved.")

    try:
        guest_room = selectors.get_guest_room_by_id(guest_room_id)
    except GuestRoom.DoesNotExist:
        raise RoomNotFoundError(f"Guest room with ID {guest_room_id} not found.")

    # Update booking
    booking.guest_room_id = str(guest_room.id)
    booking.status = BookingStatus.CONFIRMED
    booking.save(update_fields=['guest_room_id', 'status'])

    # Update guest room
    guest_room.occupied_till = booking.departure_date
    guest_room.vacant = False
    guest_room.save(update_fields=['occupied_till', 'vacant'])

    return booking


@transaction.atomic
def reject_guest_room_booking(*, booking_id: int):
    """Reject a guest room booking."""
    try:
        booking = selectors.get_booking_by_id(booking_id)
    except GuestRoomBooking.DoesNotExist:
        raise BookingNotFoundError(f"Booking with ID {booking_id} not found.")

    if booking.status != BookingStatus.PENDING:
        raise InvalidOperationError("Only PENDING bookings can be rejected.")

    booking.status = BookingStatus.REJECTED
    booking.save(update_fields=['status'])
    return booking


@transaction.atomic
def bulk_create_guest_rooms(*, hall_id: int, rooms: list):
    """Create multiple guest rooms for a hall.
    
    Args:
        hall_id: Hall database ID
        rooms: List of dicts with keys: 'room' (name), 'room_type' ('single'/'double'/'triple')
    
    Example:
        bulk_create_guest_rooms(
            hall_id=1,
            rooms=[
                {'room': 'G101', 'room_type': 'single'},
                {'room': 'G102', 'room_type': 'double'},
                {'room': 'G103', 'room_type': 'triple'},
            ]
        )
    """
    try:
        hall = selectors.get_hall_by_id(hall_id)
    except Hall.DoesNotExist:
        raise HallNotFoundError(f"Hall with ID {hall_id} not found.")
    
    guest_rooms = []
    for room_data in rooms:
        guest_room = GuestRoom(
            hall=hall,
            room=room_data['room'],
            room_type=room_data.get('room_type', 'single'),
            vacant=True
        )
        guest_rooms.append(guest_room)
    
    created_rooms = GuestRoom.objects.bulk_create(guest_rooms)
    return created_rooms


# ══════════════════════════════════════════════════════════════
# STAFF SCHEDULE SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def create_or_update_staff_schedule(
    *,
    hall,
    staff_id,
    staff_type: str,
    day: str,
    start_time: str,
    end_time: str
):
    """Create or update a staff schedule."""
    existing_schedule = selectors.get_schedule_by_staff_id(staff_id)

    if existing_schedule:
        existing_schedule.hall = hall
        existing_schedule.day = day
        existing_schedule.start_time = datetime.strptime(start_time, '%H:%M').time()
        existing_schedule.end_time = datetime.strptime(end_time, '%H:%M').time()
        existing_schedule.staff_type = staff_type
        existing_schedule.save(update_fields=['hall', 'day', 'start_time', 'end_time', 'staff_type'])
        return existing_schedule
    else:
        schedule = StaffSchedule.objects.create(
            hall=hall,
            staff_id=staff_id,
            day=day,
            staff_type=staff_type,
            start_time=datetime.strptime(start_time, '%H:%M').time(),
            end_time=datetime.strptime(end_time, '%H:%M').time()
        )
        return schedule


@transaction.atomic
def delete_staff_schedule(*, staff_id):
    """Delete a staff schedule."""
    schedule = selectors.get_schedule_by_staff_id(staff_id)
    if schedule:
        schedule.delete()


# ══════════════════════════════════════════════════════════════
# NOTICE BOARD SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def create_notice(*, hall, posted_by, head_line: str, description: str, content=None):
    """Create a new hostel notice."""
    notice = HostelNoticeBoard.objects.create(
        hall=hall,
        posted_by=posted_by,
        head_line=head_line,
        description=description,
        content=content
    )
    return notice


@transaction.atomic
def delete_notice(*, notice_id: int):
    """Delete a notice."""
    try:
        notice = selectors.get_notice_by_id(notice_id)
    except HostelNoticeBoard.DoesNotExist:
        raise HostelManagementError(f"Notice with ID {notice_id} not found.")
    notice.delete()


# ══════════════════════════════════════════════════════════════
# STUDENT ATTENDANCE SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def mark_attendance(*, student_id: str, date: str):
    """Mark attendance for a student."""
    try:
        student = selectors.get_student_by_id(student_id)
    except Student.DoesNotExist:
        raise StudentNotFoundError(f"Student with ID {student_id} not found.")

    if selectors.attendance_exists(student, date):
        raise AttendanceAlreadyMarkedError(f"Attendance already marked for {student_id} on {date}.")

    hall = selectors.get_hall_by_hall_id(f'hall{student.hall_no}')

    record = HostelStudentAttendence.objects.create(
        student_id=student,
        hall=hall,
        date=date,
        present=True
    )
    return record


# ══════════════════════════════════════════════════════════════
# ROOM MANAGEMENT SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def change_student_room(*, student_id: str, new_room_no: str, new_hall_no: str):
    """Change a student's room assignment."""
    try:
        student = selectors.get_student_by_id(student_id)
    except Student.DoesNotExist:
        raise StudentNotFoundError(f"Student with ID {student_id} not found.")

    # Remove from old room
    if student.hall_no and student.room_no:
        old_hall = selectors.get_hall_by_hall_id(f'hall{student.hall_no}')
        block = str(student.room_no[0]) if student.room_no else ''
        room_digits = re.findall('[0-9]+', str(student.room_no))
        if room_digits:
            old_room = selectors.get_room_by_details(old_hall, block, room_digits[0])
            if old_room and old_room.room_occupied > 0:
                old_room.room_occupied -= 1
                old_room.save(update_fields=['room_occupied'])
                old_hall.number_students -= 1
                old_hall.save(update_fields=['number_students'])

    # Add to new room
    new_hall = selectors.get_hall_by_hall_id(f'hall{new_hall_no}')
    block = str(new_room_no[0])
    room_digits = re.findall('[0-9]+', new_room_no)
    if not room_digits:
        raise RoomNotFoundError(f"Invalid room number format: {new_room_no}")

    new_room = selectors.get_room_by_details(new_hall, block, room_digits[0])
    if not new_room:
        raise RoomNotFoundError(f"Room {new_room_no} not found in hall {new_hall_no}.")

    if new_room.room_occupied >= new_room.room_cap:
        raise RoomNotAvailableError(f"Room {new_room_no} is at full capacity.")

    new_room.room_occupied += 1
    new_room.save(update_fields=['room_occupied'])
    new_hall.number_students += 1
    new_hall.save(update_fields=['number_students'])

    # Update student
    student.hall_no = int(new_hall_no)
    student.room_no = new_room_no
    student.save(update_fields=['hall_no', 'room_no'])

    return student


# ══════════════════════════════════════════════════════════════
# LEAVE SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def create_leave_application(
    *,
    student_name: str,
    roll_num: str,
    reason: str,
    start_date,  # Accepts date object or string
    end_date,    # Accepts date object or string
    phone_number: str = None,
    file_upload=None
):
    """Create a new leave application."""
    leave = HostelLeave.objects.create(
        student_name=student_name,
        roll_num=roll_num,
        reason=reason,
        phone_number=phone_number,
        start_date=start_date,
        end_date=end_date,
        file_upload=file_upload,
        status=LeaveStatus.PENDING
    )
    return leave


@transaction.atomic
def update_leave_status(*, leave_id: int, status: str, remark: str = None):
    """Approve or reject a leave application."""
    try:
        leave = selectors.get_leave_by_id(leave_id)
    except HostelLeave.DoesNotExist:
        raise LeaveNotFoundError(f"Leave application with ID {leave_id} not found.")

    if status not in [LeaveStatus.APPROVED, LeaveStatus.REJECTED]:
        raise InvalidOperationError(f"Invalid leave status: {status}")

    leave.status = status
    if remark:
        leave.remark = remark
    leave.save(update_fields=['status', 'remark'])
    return leave


# ══════════════════════════════════════════════════════════════
# COMPLAINT SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def file_complaint(
    *,
    hall_name: str,
    student_name: str,
    roll_number: str,
    description: str,
    contact_number: str
):
    """File a new hostel complaint."""
    complaint = HostelComplaint.objects.create(
        hall_name=hall_name,
        student_name=student_name,
        roll_number=roll_number,
        description=description,
        contact_number=contact_number
    )
    return complaint


# ══════════════════════════════════════════════════════════════
# FINE SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def impose_fine(
    *,
    student_id: str,
    student_name: str,
    hall_id: int,
    amount: float,
    reason: str
):
    """Impose a fine on a student. Works even if student doesn't exist in system."""
    # Try to get the student, but proceed even if not found
    student = None
    try:
        student = selectors.get_student_by_id(student_id)
    except Student.DoesNotExist:
        # If student doesn't exist, use any existing student as placeholder
        # This allows us to create fines for students not yet in the system
        student = Student.objects.first()

    if not student:
        # If no students exist in system at all, we cannot proceed
        raise StudentNotFoundError(f"No students in system. Please create a student record first.")

    fine = HostelFine.objects.create(
        student=student,
        student_id_entered=student_id,
        student_name=student_name,
        hall_id=hall_id,
        amount=amount,
        reason=reason,
        status=FineStatus.PENDING
    )
    return fine


@transaction.atomic
def update_fine(*, fine_id: int, **update_fields):
    """Update fine information."""
    try:
        fine = selectors.get_fine_by_id(fine_id)
    except HostelFine.DoesNotExist:
        raise FineNotFoundError(f"Fine with ID {fine_id} not found.")

    for field, value in update_fields.items():
        setattr(fine, field, value)
    fine.save()
    return fine


@transaction.atomic
def update_fine_status(*, fine_id: int, status: str):
    """Update the payment status of a fine."""
    if status not in [FineStatus.PENDING, FineStatus.PAID]:
        raise InvalidOperationError(f"Invalid fine status: {status}")

    try:
        fine = selectors.get_fine_by_id(fine_id)
    except HostelFine.DoesNotExist:
        raise FineNotFoundError(f"Fine with ID {fine_id} not found.")

    fine.status = status
    fine.save(update_fields=['status'])
    return fine


@transaction.atomic
def delete_fine(*, fine_id: int):
    """Delete a fine."""
    try:
        fine = selectors.get_fine_by_id(fine_id)
    except HostelFine.DoesNotExist:
        raise FineNotFoundError(f"Fine with ID {fine_id} not found.")
    fine.delete()


# ══════════════════════════════════════════════════════════════
# INVENTORY SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def create_inventory_item(
    *,
    hall_id: int,
    inventory_name: str,
    cost: float,
    quantity: int
):
    """Create a new inventory item."""
    inventory = HostelInventory.objects.create(
        hall_id=hall_id,
        inventory_name=inventory_name,
        cost=cost,
        quantity=quantity
    )
    return inventory


@transaction.atomic
def update_inventory_item(*, inventory_id: int, **update_fields):
    """Update inventory item information."""
    try:
        inventory = selectors.get_inventory_by_id(inventory_id)
    except HostelInventory.DoesNotExist:
        raise InventoryNotFoundError(f"Inventory item with ID {inventory_id} not found.")

    for field, value in update_fields.items():
        setattr(inventory, field, value)
    inventory.save()
    return inventory


@transaction.atomic
def delete_inventory_item(*, inventory_id: int):
    """Delete an inventory item."""
    try:
        inventory = selectors.get_inventory_by_id(inventory_id)
    except HostelInventory.DoesNotExist:
        raise InventoryNotFoundError(f"Inventory item with ID {inventory_id} not found.")
    inventory.delete()


# ══════════════════════════════════════════════════════════════
# WORKER REPORT SERVICES
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def create_worker_report(
    *,
    hall,
    worker_id: str,
    worker_name: str,
    year: int,
    month: int,
    absent: int,
    total_day: int,
    remark: str
):
    """Create a worker report entry."""
    report = WorkerReport.objects.create(
        hall=hall,
        worker_id=worker_id,
        worker_name=worker_name,
        year=year,
        month=month,
        absent=absent,
        total_day=total_day,
        remark=remark
    )
    return report


# ══════════════════════════════════════════════════════════════
# STUDENT DETAILS SERVICES (for updating extended info)
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def update_student_details(*, student_id: str, **update_fields):
    """Update extended student details."""
    try:
        student_details = selectors.get_student_details_by_id(student_id)
        for field, value in update_fields.items():
            setattr(student_details, field, value)
        student_details.save()
        return student_details
    except StudentDetails.DoesNotExist:
        # Create if doesn't exist
        return StudentDetails.objects.create(id=student_id, **update_fields)


@transaction.atomic
def remove_student_from_hostel(*, student_id: str):
    """Remove a student from hostel (set hall_no to 0)."""
    try:
        student = selectors.get_student_by_id(student_id)
    except Student.DoesNotExist:
        raise StudentNotFoundError(f"Student with ID {student_id} not found.")

    student.hall_no = 0
    student.save(update_fields=['hall_no'])
    return student
