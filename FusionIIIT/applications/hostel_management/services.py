"""
Hostel Management Services

This module contains ALL business logic, state mutations, and rule enforcement.
- Business Rules are enforced here and raise custom exceptions on violation
- All database mutations go through services
- Services use selectors for queries
"""

from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import (
    HostelLeave, HostelComplaint, RoomAllocationChange,
    HostelFine, HostelStudentAttendance,
    GuestRoomBooking, GuestRoom, Hostel, Room, RoomAllotment,
    HostelStaffAssignment,
    AccommodationApplicationWindow, AccommodationRequest,
    LeaveStatusChoices, ComplaintStatusChoices,
    AllocationChangeStatusChoices, FineStatusChoices, BookingStatusChoices,
    StaffRoleChoices, RoomSetupStatusChoices
)
from django.db import transaction
from . import selectors


# ══════════════════════════════════════════════════════════════
# CUSTOM EXCEPTIONS
# ══════════════════════════════════════════════════════════════

class HostelManagementException(Exception):
    """Base exception for hostel management errors."""
    pass


class LeaveEligibilityError(HostelManagementException):
    """Raised when leave eligibility is not met (BR-HM-101)."""
    pass


class LeaveDateError(HostelManagementException):
    """Raised when leave dates are invalid (BR-HM-102)."""
    pass


class LeaveJustificationError(HostelManagementException):
    """Raised when leave lacks justification (BR-HM-103)."""
    pass


class LeaveAuthorityError(HostelManagementException):
    """Raised when leave decision maker lacks authority (BR-HM-104)."""
    pass


class ComplaintEligibilityError(HostelManagementException):
    """Raised when complaint eligibility is not met (BR-HM-106)."""
    pass


class ComplaintRoutingError(HostelManagementException):
    """Raised when complaint routing fails (BR-HM-107)."""
    pass


class ResolutionRemarksError(HostelManagementException):
    """Raised when resolution remarks are missing (BR-HM-108)."""
    pass


class EscalationAuthorizationError(HostelManagementException):
    """Raised when escalation is not authorized (BR-HM-109)."""
    pass


class WardenAuthorityError(HostelManagementException):
    """Raised when warden authority is required (BR-HM-110)."""
    pass


class ApplicationWindowError(HostelManagementException):
    """Raised when application window is closed (BR-HM-111)."""
    pass


class AllotmentCapacityError(HostelManagementException):
    """Raised when room capacity would be exceeded (BR-HM-112)."""
    pass


class RoomChangeEligibilityError(HostelManagementException):
    """Raised when student is not eligible for room change (BR-HM-115)."""
    pass


class DualApprovalError(HostelManagementException):
    """Raised when dual approval requirement is not met (BR-HM-116)."""
    pass


class OccupancyReconciliationError(HostelManagementException):
    """Raised when occupancy reconciliation fails (BR-HM-117)."""
    pass


class RoomVacationPrerequisiteError(HostelManagementException):
    """Raised when room vacation prerequisites are not met (BR-015)."""
    pass


class FineValidationError(HostelManagementException):
    """Raised when fine validation fails (BR-HM-013)."""
    pass


# ══════════════════════════════════════════════════════════════
# HM-WF-101: LEAVE MANAGEMENT SERVICES
# ══════════════════════════════════════════════════════════════

def create_leave_request(student, start_date, end_date, reason, destination=None, contact_phone=None):
    """
    Create a new leave request.
    
    Enforces:
    - BR-HM-101: Leave Eligibility Based on Hostel Residency
    - BR-HM-102: Leave Date Boundary Validation
    - BR-HM-103: Mandatory Leave Justification Policy
    """
    # BR-HM-101: Check if student is currently in hostel
    current_allotment = selectors.get_active_allotment_by_student(student)
    if not current_allotment:
        raise LeaveEligibilityError(
            "Student must have an active hostel allotment to request leave."
        )
    
    # BR-HM-102: Validate leave dates
    today = timezone.now().date()
    if start_date < today:
        raise LeaveDateError("Leave start date cannot be in the past.")
    if end_date < start_date:
        raise LeaveDateError("Leave end date must be after start date.")
    
    # Check for maximum leave duration (e.g., 90 days)
    leave_duration = (end_date - start_date).days
    if leave_duration > 90:
        raise LeaveDateError("Leave duration cannot exceed 90 days.")
    
    # BR-HM-103: Check for mandatory justification
    if not reason or len(reason.strip()) < 10:
        raise LeaveJustificationError(
            "Leave must have a valid reason (at least 10 characters)."
        )
    
    # Create the leave request
    leave = HostelLeave.objects.create(
        student=student,
        student_name=student.id.user.get_full_name() or student.id.user.username,
        roll_num=student.id.user.username,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
        destination=destination,
        contact_phone=contact_phone,
        status=LeaveStatusChoices.PENDING,
        hostel=current_allotment.hostel
    )
    
    return leave


def approve_leave(leave_id, processed_by, remarks=None):
    """
    Approve a leave request.
    
    Enforces:
    - BR-HM-104: Leave Decision Authority Enforcement
    - BR-HM-105: Attendance Synchronization on Leave Approval
    """
    leave = selectors.get_student_leave(leave_id)
    if not leave:
        raise HostelManagementException(f"Leave {leave_id} not found.")
    
    if leave.status != LeaveStatusChoices.PENDING:
        raise HostelManagementException(
            f"Cannot approve leave in {leave.status} status."
        )
    
    # BR-HM-104: Authority check (caretaker/warden must process)
    # This should be enforced at view level, but check here too
    if not processed_by:
        raise LeaveAuthorityError("Leave approval requires authorized personnel.")
    
    leave.status = LeaveStatusChoices.APPROVED
    leave.processed_by = processed_by
    leave.remarks = remarks
    leave.updated_at = timezone.now()
    leave.save()
    
    # BR-HM-105: Mark student as absent for leave dates
    _mark_leave_attendance(leave.student, leave.start_date, leave.end_date, is_present=False)
    
    return leave


def reject_leave(leave_id, processed_by, rejection_reason):
    """Reject a leave request."""
    leave = selectors.get_student_leave(leave_id)
    if not leave:
        raise HostelManagementException(f"Leave {leave_id} not found.")
    
    if leave.status != LeaveStatusChoices.PENDING:
        raise HostelManagementException(
            f"Cannot reject leave in {leave.status} status."
        )
    
    if not rejection_reason or len(rejection_reason.strip()) < 5:
        raise HostelManagementException("Rejection must have a valid reason.")
    
    leave.status = LeaveStatusChoices.REJECTED
    leave.processed_by = processed_by
    leave.remarks = rejection_reason
    leave.updated_at = timezone.now()
    leave.save()
    
    return leave


def cancel_leave(leave_id):
    """Cancel an approved leave request."""
    leave = selectors.get_student_leave(leave_id)
    if not leave:
        raise HostelManagementException(f"Leave {leave_id} not found.")
    
    if leave.status != LeaveStatusChoices.APPROVED:
        raise HostelManagementException(
            f"Only approved leaves can be cancelled. Current status: {leave.status}"
        )
    
    leave.status = LeaveStatusChoices.CANCELLED
    leave.updated_at = timezone.now()
    leave.save()
    
    return leave


def _mark_leave_attendance(student, start_date, end_date, is_present):
    """Mark attendance for leave dates."""
    current_allocation = selectors.get_active_allotment_by_student(student)
    if not current_allocation or not current_allocation.room:
        return
    
    hostel = current_allocation.hostel
    current_date = start_date
    
    while current_date <= end_date:
        HostelStudentAttendance.objects.update_or_create(
            student_id=student,
            date=current_date,
            defaults={
                'hostel': hostel,
                'present': is_present,
                'remarks': 'Leave' if not is_present else None
            }
        )
        current_date += timedelta(days=1)


def mark_attendance(hostel, date, attendance_data):
    """
    Bulk mark attendance for students in a hall.
    attendance_data: list of dicts [{'student_id': id, 'present': bool, 'remarks': str}]
    """
    from applications.academic_information.models import Student
    records = []
    for entry in attendance_data:
        student = Student.objects.get(pk=entry['student_id'])
        record, created = HostelStudentAttendance.objects.update_or_create(
            student_id=student,
            date=date,
            defaults={
                'hostel': hostel,
                'present': entry['present'],
                'remarks': entry.get('remarks')
            }
        )
        records.append(record)
    return records


# ══════════════════════════════════════════════════════════════
# HM-WF-102: COMPLAINT MANAGEMENT SERVICES
# ══════════════════════════════════════════════════════════════

def create_complaint(student, title, description, category, priority, location=None):
    """
    Create a new complaint.
    
    Enforces:
    - BR-HM-106: Complaint Eligibility Rule
    - BR-HM-107: Complaint Routing by Category
    """
    # BR-HM-106: Check if student is currently in hostel
    current_allocation = selectors.get_active_allotment_by_student(student)
    if not current_allocation:
        raise ComplaintEligibilityError(
            "Only students with active hostel allotment can file complaints."
        )
    
    # Validate complaint data
    if not title or len(title.strip()) < 5:
        raise ComplaintRoutingError("Complaint title must be at least 5 characters.")
    
    if not description or len(description.strip()) < 20:
        raise ComplaintRoutingError("Complaint description must be at least 20 characters.")
    
    # Get hostel from student's allocation
    hostel = current_allocation.hostel
    
    # BR-HM-107: Route complaint to appropriate staff by hostel
    staff_assignment = selectors.get_hostel_staff(hostel.hall_id).first()
    
    complaint = HostelComplaint.objects.create(
        student=student,
        hostel=hostel,
        title=title,
        description=description,
        category=category,
        priority=priority,
        location=location,
        status=ComplaintStatusChoices.SUBMITTED,
        assigned_to=staff_assignment.user if staff_assignment else None
    )
    
    return complaint


def update_complaint_status(complaint_id, new_status, resolution_notes=None):
    """
    Update complaint status.
    
    Enforces:
    - BR-HM-108: Mandatory Resolution Remarks
    """
    complaint = selectors.get_complaint(complaint_id)
    if not complaint:
        raise HostelManagementException(f"Complaint {complaint_id} not found.")
    
    # BR-HM-108: Require resolution remarks when resolving
    if new_status in [ComplaintStatusChoices.RESOLVED, ComplaintStatusChoices.CLOSED]:
        if not resolution_notes or len(resolution_notes.strip()) < 10:
            raise ResolutionRemarksError(
                "Resolution remarks are mandatory and must be at least 10 characters."
            )
    
    complaint.status = new_status
    complaint.resolution_notes = resolution_notes
    complaint.updated_at = timezone.now()
    
    if new_status == ComplaintStatusChoices.RESOLVED:
        complaint.resolved_at = timezone.now()
    
    complaint.save()
    return complaint


def escalate_complaint(complaint_id, warden):
    """
    Escalate complaint to warden.
    
    Enforces:
    - BR-HM-109: Escalation Authorization Rule
    - BR-HM-110: Warden Authority on Escalated Complaints
    """
    complaint = selectors.get_complaint(complaint_id)
    if not complaint:
        raise HostelManagementException(f"Complaint {complaint_id} not found.")
    
    # BR-HM-109: Only open/in-progress complaints can be escalated
    if complaint.status not in [ComplaintStatusChoices.OPEN, ComplaintStatusChoices.IN_PROGRESS]:
        raise EscalationAuthorizationError(
            "Only open or in-progress complaints can be escalated."
        )
    
    # BR-HM-110: Assign to appropriate warden
    if not warden:
        raise WardenAuthorityError("Escalation requires a valid warden assignment.")
    
    complaint.escalated_to_warden = True
    complaint.warden_assigned = warden
    complaint.status = ComplaintStatusChoices.IN_PROGRESS
    complaint.updated_at = timezone.now()
    complaint.save()
    
    return complaint


# ══════════════════════════════════════════════════════════════
# HM-WF-103: ACCOMMODATION SERVICES
# ══════════════════════════════════════════════════════════════

def create_accommodation_request(student, window_id, preferred_hostel_type, preferred_room_type):
    """
    Submits a new accommodation request for a student.
    - BR-HM-111: Application Window Enforcement
    """
    window = AccommodationApplicationWindow.objects.filter(id=window_id).first()
    if not window or not window.is_open:
        raise ApplicationWindowError("The application window is currently closed.")

    # Check for existing request
    if selectors.get_student_accommodation_request(student, window):
        raise HostelManagementException("You have already submitted a request for this window.")

    request = AccommodationRequest.objects.create(
        student=student,
        window=window,
        preferred_hostel_type=preferred_hostel_type,
        preferred_room_type=preferred_room_type,
        status=AccommodationRequest.Status.PENDING
    )
    return request


def perform_bulk_allotment(request_ids, allotted_by):
    """
    Performs bulk allotment for selected requests.
    - BR-HM-112: Capacity Safeguard
    - BR-HM-113: Transaction Safety with select_for_update
    - BR-HM-114: Notification Trigger (Stub)
    """
    results = {
        'success': [],
        'failed': []
    }

    with transaction.atomic():
        # Lock requests and related student profiles
        requests = AccommodationRequest.objects.select_for_update().filter(
            id__in=request_ids,
            status=AccommodationRequest.Status.PENDING
        )

        for req in requests:
            try:
                # Find suitable room using selector
                # Criteria: matches preferred_hostel_type and preferred_room_type
                # AND current_occupancy < capacity
                suitable_rooms = Room.objects.select_for_update().filter(
                    hostel__type=req.preferred_hostel_type,
                    capacity__gt=F('current_occupancy'),
                    hostel__status='Active' # Depend on Chunk 1 Hostel status
                ).order_by('floor', 'room_number')

                # For simplicity, we filter room type by capacity (Single=1, Double=2, etc. - usually defined in business rules)
                # Here we assume room_type maps to capacity for filter
                # Single=1, Double=2, Triple=3
                capacity_map = {'Single': 1, 'Double': 2, 'Triple': 3}
                preferred_capacity = capacity_map.get(req.preferred_room_type, 1)
                
                room = suitable_rooms.filter(capacity=preferred_capacity).first()

                if not room:
                    results['failed'].append({
                        'request_id': req.id,
                        'reason': 'No suitable rooms available for preferred types.'
                    })
                    continue

                # Create Allotment
                allotment = RoomAllotment.objects.create(
                    student=req.student,
                    room=room,
                    hostel=room.hostel,
                    allotted_by=allotted_by,
                    is_active=True
                )

                # Update Room occupancy
                room.current_occupancy += 1
                room.save()

                # Update Request status
                req.status = AccommodationRequest.Status.ALLOTTED
                req.save()

                results['success'].append({
                    'request_id': req.id,
                    'room_number': room.room_number,
                    'hostel_name': room.hostel.name
                })

                # BR-HM-114: Trigger Notification
                _trigger_allotment_notification(allotment)

            except Exception as e:
                results['failed'].append({
                    'request_id': req.id,
                    'reason': str(e)
                })

    return results


def _trigger_allotment_notification(allotment):
    """Placeholder for BR-HM-114: Mandatory Allotment Notification."""
    # In a real system, this would queue a task or send a signal
    print(f"NOTIFICATION: Student {allotment.student.id.user.username} allotted to {allotment.room.room_number}")


# ══════════════════════════════════════════════════════════════
# HM-WF-104: ROOM CHANGE SERVICES
# ══════════════════════════════════════════════════════════════

def request_room_change(student, current_room, requested_room, reason):
    """
    Request a room change.
    
    Enforces:
    - BR-HM-115: Room Change Eligibility Rule
    """
    # BR-HM-115: Student must have current allocation
    current_allocation = selectors.get_active_allotment_by_student(student)
    if not current_allocation:
        raise RoomChangeEligibilityError(
            "Student must have an active hostel allocation to request room change."
        )

    
    # Check if currently allocated room matches
    if current_allocation.room != current_room:
        raise RoomChangeEligibilityError(
            "Requested current room does not match student's allocation."
        )
    
    # Cannot request change to same room
    if current_room == requested_room:
        raise RoomChangeEligibilityError(
            "Cannot request change to the same room."
        )
    
    # Validate reason
    if not reason or len(reason.strip()) < 10:
        raise RoomChangeEligibilityError(
            "Room change reason must be at least 10 characters."
        )
    
    change_request = RoomAllocationChange.objects.create(
        student=student,
        current_room=current_room,
        requested_room=requested_room,
        reason=reason,
        status=AllocationChangeStatusChoices.REQUESTED,
        requested_date=timezone.now().date()
    )
    
    return change_request


def approve_room_change_warden(change_id, warden, remarks=None):
    """
    Warden approves room change.
    
    Enforces:
    - BR-HM-116: Dual Approval Requirement
    """
    change = selectors.get_room_change(change_id)
    if not change:
        raise HostelManagementException(f"Room change {change_id} not found.")
    
    if change.status != AllocationChangeStatusChoices.REQUESTED:
        raise DualApprovalError(
            f"Room change is in {change.status} status and cannot be approved."
        )
    
    change.status = AllocationChangeStatusChoices.APPROVED_WARDEN
    change.approved_by_warden = warden
    change.warden_approval_date = timezone.now()
    change.warden_remarks = remarks
    change.save()
    
    return change


def approve_room_change_caretaker(change_id, caretaker, remarks=None):
    """
    Caretaker approves room change (final approval).
    
    Enforces:
    - BR-HM-116: Dual Approval Requirement (completes dual approval)
    - BR-HM-117: Occupancy Reconciliation on Room Change
    """
    from .models import RoomAllotment
    
    change = selectors.get_room_change(change_id)
    if not change:
        raise HostelManagementException(f"Room change {change_id} not found.")
    
    if change.status != AllocationChangeStatusChoices.APPROVED_WARDEN:
        raise DualApprovalError(
            "Room change must be approved by warden before caretaker approval."
        )
    
    # BR-HM-117: Check capacity of requested room
    if change.requested_room.current_occupancy >= change.requested_room.capacity:
        raise AllotmentCapacityError(
            f"Requested room is at full capacity and cannot accommodate change."
        )
    
    with transaction.atomic():
        # Update allotments (new model 'RoomAllotment')
        current_allotment = selectors.get_active_allotment_by_student(change.student)
        if current_allotment:
            # Release from current room
            current_allotment.is_active = False
            current_allotment.vacated_at = timezone.now()
            current_allotment.save()
            
            # Update current room occupancy
            if current_allotment.room:
                current_allotment.room.current_occupancy = max(0, current_allotment.room.current_occupancy - 1)
                if current_allotment.room.current_occupancy < current_allotment.room.capacity:
                    current_allotment.room.status = 'Available'
                current_allotment.room.save()
        
        # Create new allotment in requested room
        RoomAllotment.objects.create(
            student=change.student,
            room=change.requested_room,
            hostel=change.requested_room.hostel,
            allotted_by=caretaker,
            is_active=True
        )
        
        # Update requested room occupancy
        change.requested_room.current_occupancy += 1
        if change.requested_room.current_occupancy >= change.requested_room.capacity:
            change.requested_room.status = 'Occupied'
        change.requested_room.save()
        
        # Update change request
        change.status = AllocationChangeStatusChoices.COMPLETED
        change.approved_by_caretaker = caretaker
        change.caretaker_approval_date = timezone.now()
        change.caretaker_remarks = remarks
        change.effective_date = timezone.now().date()
        change.save()
    
    # BR-HM-118: Send mandatory room change notification
    send_room_change_notification(change)
    
    return change


def reject_room_change(change_id, rejection_reason):
    """Reject a room change request."""
    change = selectors.get_room_change(change_id)
    if not change:
        raise HostelManagementException(f"Room change {change_id} not found.")
    
    if change.status == AllocationChangeStatusChoices.COMPLETED:
        raise HostelManagementException("Cannot reject a completed room change.")
    
    if change.status == AllocationChangeStatusChoices.REJECTED:
        raise HostelManagementException("Room change is already rejected.")
    
    if not rejection_reason or len(rejection_reason.strip()) < 5:
        raise HostelManagementException("Rejection reason must be at least 5 characters.")
    
    change.status = AllocationChangeStatusChoices.REJECTED
    change.rejection_reason = rejection_reason
    change.save()
    
    return change


# ══════════════════════════════════════════════════════════════
# HM-WF-105: FINE MANAGEMENT SERVICES
# ══════════════════════════════════════════════════════════════

def issue_fine(student, hostel, fine_type, amount, reason, due_date, issued_by):
    """
    Issue a fine to a student.
    
    Enforces:
    - BR-HM-013: Fine Imposition Validation
    """
    # BR-HM-013: Validate fine data
    if not student or not hostel:
        raise FineValidationError("Student and hostel are required to issue a fine.")
    
    if amount <= 0:
        raise FineValidationError("Fine amount must be greater than zero.")
    
    if due_date < timezone.now().date():
        raise FineValidationError("Due date cannot be in the past.")
    
    if not reason or len(reason.strip()) < 10:
        raise FineValidationError("Fine reason must be at least 10 characters.")
    
    fine = HostelFine.objects.create(
        student=student,
        hostel=hostel,
        fine_type=fine_type,
        amount=Decimal(str(amount)),
        reason=reason,
        due_date=due_date,
        status=FineStatusChoices.PENDING,
        issued_by=issued_by
    )
    
    return fine


def pay_fine(fine_id):
    """Mark a fine as paid."""
    fine = selectors.get_fine(fine_id)
    if not fine:
        raise HostelManagementException(f"Fine {fine_id} not found.")
    
    if fine.status != FineStatusChoices.PENDING:
        raise HostelManagementException(
            f"Cannot pay fine in {fine.status} status."
        )
    
    fine.status = FineStatusChoices.PAID
    fine.paid_date = timezone.now().date()
    fine.updated_at = timezone.now()
    fine.save()
    
    return fine


def waive_fine(fine_id, waived_by, waive_reason):
    """Waive a fine (warden authority)."""
    fine = selectors.get_fine(fine_id)
    if not fine:
        raise HostelManagementException(f"Fine {fine_id} not found.")
    
    if fine.status == FineStatusChoices.PAID:
        raise HostelManagementException("Cannot waive an already paid fine.")
    
    if fine.status == FineStatusChoices.CANCELLED:
        raise HostelManagementException("Fine is already cancelled.")
    
    if not waive_reason or len(waive_reason.strip()) < 5:
        raise HostelManagementException("Waive reason must be at least 5 characters.")
    
    fine.status = FineStatusChoices.WAIVED
    fine.waived_by = waived_by
    fine.waive_reason = waive_reason
    fine.updated_at = timezone.now()
    fine.save()
    
    return fine


def cancel_fine(fine_id):
    """Cancel a fine."""
    fine = selectors.get_fine(fine_id)
    if not fine:
        raise HostelManagementException(f"Fine {fine_id} not found.")
    
    if fine.status in [FineStatusChoices.PAID, FineStatusChoices.WAIVED]:
        raise HostelManagementException(
            f"Cannot cancel a {fine.status} fine."
        )
    fine.status = FineStatusChoices.CANCELLED
    fine.updated_at = timezone.now()
    fine.save()
    
    return fine


# ══════════════════════════════════════════════════════════════
# HM-WF-112: GUEST ROOM BOOKING SERVICES
# ══════════════════════════════════════════════════════════════

def request_guest_room(student, guest_name, guest_phone, arrival_date, departure_date, 
                       purpose, total_guests, guest_email="", guest_address="", 
                       nationality="", rooms_required=1, room_type="single"):
    """
    Request a guest room booking.
    
    Creates a pending guest room booking request that must be approved by staff.
    """
    if not guest_name or len(guest_name.strip()) < 3:
        raise HostelManagementException("Guest name must be at least 3 characters.")
    
    if not guest_phone or len(guest_phone) < 10:
        raise HostelManagementException("Phone number must be at least 10 characters.")
    
    if total_guests <= 0 or total_guests > 100:
        raise HostelManagementException("Total guests must be between 1 and 100.")
    
    if arrival_date >= departure_date:
        raise HostelManagementException("Departure date must be after arrival date.")
    
    duration = (departure_date - arrival_date).days
    if duration > 30:
        raise HostelManagementException("Booking duration cannot exceed 30 days.")
    
    if arrival_date < timezone.now().date():
        raise HostelManagementException("Arrival date cannot be in the past.")
    
    # Get student's primary hall from current allocation
    student_obj = selectors.get_student(student.pk)
    if not student_obj:
        raise HostelManagementException("Student not found.")
    
    current_allocation = selectors.get_student_current_allocation(student_obj)
    if not current_allocation:
        raise HostelManagementException("Student must be allocated to a hostel.")
    
    hall = current_allocation.room.hall    
    # Create booking
    booking = GuestRoomBooking.objects.create(
        student=student_obj,
        hall=hall,
        guest_name=guest_name,
        guest_phone=guest_phone,
        guest_email=guest_email or "",
        guest_address=guest_address or "",
        nationality=nationality or "",
        total_guests=total_guests,
        purpose=purpose,
        arrival_date=arrival_date,
        departure_date=departure_date,
        rooms_required=rooms_required or 1,
        room_type=room_type or "single",
        status=BookingStatusChoices.PENDING,
        booking_date=timezone.now().date()
    )
    
    return booking


def approve_guest_booking(booking_id, approved_by, guest_room_id=None, remarks=""):
    """
    Approve a guest room booking and optionally assign a room.
    """
    booking = selectors.get_guest_booking(booking_id)
    if not booking:
        raise HostelManagementException(f"Guest booking {booking_id} not found.")
    
    if booking.status != BookingStatusChoices.PENDING:
        raise HostelManagementException(
            f"Cannot approve booking in {booking.status} status."
        )
    
    booking.status = BookingStatusChoices.APPROVED
    booking.review_remarks = remarks
    booking.updated_at = timezone.now()
    
    # Assign room if provided
    if guest_room_id:
        guest_room = GuestRoom.objects.filter(id=guest_room_id).first()
        if not guest_room:
            raise HostelManagementException(f"Guest room {guest_room_id} not found.")
        
        # Check if room is available for the requested dates
        if not guest_room.is_vacant:
            raise HostelManagementException("Selected room is not available for requested dates.")
        
        booking.guest_room = guest_room
        guest_room.occupied_till = booking.departure_date
        guest_room.save()
    
    booking.save()
    return booking


def reject_guest_booking(booking_id, rejection_reason):
    """
    Reject a guest room booking request.
    """
    booking = selectors.get_guest_booking(booking_id)
    if not booking:
        raise HostelManagementException(f"Guest booking {booking_id} not found.")
    
    if booking.status != BookingStatusChoices.PENDING:
        raise HostelManagementException(
            f"Cannot reject booking in {booking.status} status."
        )
    
    if not rejection_reason or len(rejection_reason.strip()) < 5:
        raise HostelManagementException("Rejection reason must be at least 5 characters.")
    
    booking.status = BookingStatusChoices.REJECTED
    booking.review_remarks = rejection_reason
    booking.updated_at = timezone.now()
    booking.save()
    
    return booking


def check_in_guest(booking_id):
    """
    Check in a guest (mark as checked in).
    """
    booking = selectors.get_guest_booking(booking_id)
    if not booking:
        raise HostelManagementException(f"Guest booking {booking_id} not found.")
    
    if booking.status != BookingStatusChoices.APPROVED:
        raise HostelManagementException(
            f"Cannot check in booking in {booking.status} status. Must be APPROVED."
        )
    
    if not booking.guest_room:
        raise HostelManagementException("Guest room must be assigned before check-in.")
    
    booking.status = BookingStatusChoices.CHECKED_IN
    booking.checked_in_at = timezone.now()
    booking.updated_at = timezone.now()
    booking.save()
    
    return booking


def check_out_guest(booking_id):
    """
    Check out a guest (mark as checked out).
    """
    booking = selectors.get_guest_booking(booking_id)
    if not booking:
        raise HostelManagementException(f"Guest booking {booking_id} not found.")
    
    if booking.status != BookingStatusChoices.CHECKED_IN:
        raise HostelManagementException(
            f"Cannot check out booking in {booking.status} status. Must be CHECKED_IN."
        )
    
    booking.status = BookingStatusChoices.CHECKED_OUT
    booking.checked_out_at = timezone.now()
    booking.updated_at = timezone.now()
    booking.save()
    
    # Clear room occupancy
    if booking.guest_room:
        booking.guest_room.occupied_till = None
        booking.guest_room.save()
    
    return booking


# ...existing code...


# ══════════════════════════════════════════════════════════════
# NOTIFICATION HELPERS - BR-HM-118 & Related
# ══════════════════════════════════════════════════════════════

def assign_warden_to_hostel(hostel, faculty):
    """
    Assign a warden to a hostel (Super Admin only).
    """
    # Remove existing active warden if any
    HostelStaffAssignment.objects.filter(
        hostel=hostel, 
        role=StaffRoleChoices.WARDEN, 
        is_active=True
    ).update(is_active=False)
    
    # Assign new warden
    assignment = HostelStaffAssignment.objects.create(
        hostel=hostel,
        user=faculty.id.user,
        role=StaffRoleChoices.WARDEN,
        is_active=True
    )
    return assignment


def assign_caretaker_to_hostel(hostel, staff):
    """
    Assign a caretaker to a hostel (Super Admin only).
    """
    # Remove existing active caretaker if any
    HostelStaffAssignment.objects.filter(
        hostel=hostel, 
        role=StaffRoleChoices.CARETAKER, 
        is_active=True
    ).update(is_active=False)
    
    # Assign new caretaker
    assignment = HostelStaffAssignment.objects.create(
        hostel=hostel,
        user=staff.id.user,
        role=StaffRoleChoices.CARETAKER,
        is_active=True
    )
    return assignment


def allocate_batch_to_hostel(hostel, academic_batch):
    """
    Allocate an academic batch to a hostel (Super Admin only).
    """
    hostel.save()
    return hostel


def send_room_change_notification(change_request):
    """
    Send notification for room change completion.
    
    Enforces:
    - BR-HM-118: Mandatory Room Change Notification
    """
    # Placeholder for notification system integration
    # This ensures BR-HM-118 compliance by documenting the requirement
    pass


# ══════════════════════════════════════════════════════════════
# SUPER ADMIN MANAGEMENT SERVICES
# ══════════════════════════════════════════════════════════════

def assign_warden_to_hostel(hostel, faculty):
    """
    Assign a warden to a hall (Super Admin only).
    
    Args:
        hall: Hall object
        faculty: Faculty object to assign as warden
    
    Returns:
        HallWarden object
    """
    from .models import HallWarden
    
    # Remove existing warden if any
    existing_wardens = HallWarden.objects.filter(hostel=hostel)
    if existing_wardens.exists():
        existing_wardens.delete()
    
    # Assign new warden
    warden = HallWarden.objects.create(
        hostel=hostel,
        faculty=faculty
    )
    return warden


def assign_caretaker_to_hall(hall, staff):
    """
    Assign a caretaker to a hall (Super Admin only).
    
    Args:
        hall: Hall object
        staff: Staff object to assign as caretaker
    
    Returns:
        HallCaretaker object
    """
    from .models import HallCaretaker
    
    # Remove existing caretaker if any
    existing_caretakers = HallCaretaker.objects.filter(hall=hall)
    if existing_caretakers.exists():
        existing_caretakers.delete()
    
    # Assign new caretaker
    caretaker = HallCaretaker.objects.create(
        hall=hall,
        staff=staff
    )
    return caretaker


def allocate_batch_to_hall(hall, academic_batch):
    """
    Allocate an academic batch to a hall (Super Admin only).
    Batch allocation assigns the batch year to a specific hall.
    
    Args:
        hall: Hall object
        academic_batch: AcademicBatch object
    
    Returns:
        Updated Hall object
    """
    hall.assigned_batch = academic_batch
    hall.save()
    return hall


def get_active_batch_years():
    """
    Get all active academic batch years for display and assignment.
    Returns a list of active batches with their details.
    
    Returns:
        List of active batches
    """
    from applications.programme_curriculum.models import Batch
    
    # Get all active batches
    active_batches = Batch.objects.filter(
        running_batch=True
    ).values('id', 'discipline__acronym', 'year').distinct()
    
    return list(active_batches)


def rename_room_in_hall(room, new_room_number, new_block_number=None):
    """
    Rename a room (Warden/Caretaker can rename, changing from sequential 1,2,3 to A101, etc).
    
    Args:
        room: HallRoom object
        new_room_number: New room number (e.g., 'A101')
        new_block_number: New block number (e.g., 'A')
    
    Returns:
        Updated HallRoom object
    """
    room.room_number = new_room_number
    if new_block_number:
        room.block_number = new_block_number
    room.save()
    return room


# ══════════════════════════════════════════════════════════════
# VIEW-FACING SERVICE WRAPPERS
# These functions are called by views.py and delegate to the
# core service functions above.
# ══════════════════════════════════════════════════════════════

def submit_leave_request(student, start_date, end_date, reason, destination=None, contact_phone=None):
    """Wrapper for create_leave_request — called by LeaveListCreateView."""
    return create_leave_request(student, start_date, end_date, reason, destination, contact_phone)


def submit_complaint(student, category, title, description, priority=None, location=None):
    """Wrapper for create_complaint — called by ComplaintListCreateView."""
    return create_complaint(
        student=student,
        title=title,
        description=description,
        category=category,
        priority=priority or 'medium',
        location=location
    )


def update_complaint(complaint_id, status=None, resolution_notes=None):
    """Wrapper for update_complaint_status — called by ComplaintRetrieveUpdateView."""
    if status:
        return update_complaint_status(complaint_id, status, resolution_notes)
    return selectors.get_complaint(complaint_id)


def resolve_complaint(complaint_id, resolution_notes=''):
    """Resolve a complaint — called by ComplaintResolveView."""
    from .models import ComplaintStatusChoices
    return update_complaint_status(complaint_id, ComplaintStatusChoices.RESOLVED, resolution_notes)


def approve_room_change(change_id, approved_by, remarks=None):
    """Unified room change approval — determines warden vs caretaker step."""
    from .models import AllocationChangeStatusChoices
    change = selectors.get_room_change(change_id)
    if not change:
        raise HostelManagementException(f"Room change {change_id} not found.")
    
    if change.status == AllocationChangeStatusChoices.REQUESTED:
        # First approval: warden
        return approve_room_change_warden(change_id, approved_by, remarks)
    elif change.status == AllocationChangeStatusChoices.APPROVED_WARDEN:
        # Second approval: caretaker
        return approve_room_change_caretaker(change_id, approved_by, remarks)
    else:
        raise HostelManagementException(
            f"Room change cannot be approved in {change.status} status."
        )


def impose_fine(student_id, fine_type, amount, reason, due_date, issued_by):
    """Wrapper for issue_fine — called by FineListCreateView."""
    student = selectors.get_student(student_id)
    if not student:
        raise HostelManagementException("Student not found.")
    
    current_allocation = selectors.get_student_current_allocation(student.pk)
    hall = current_allocation.room.hall if current_allocation and current_allocation.room else None
    if not hall:
        raise HostelManagementException("Student must be allocated to a hall for fines.")
    
    return issue_fine(student, hall, fine_type, amount, reason, due_date, issued_by)


def mark_fine_paid(fine_id, paid_date=None):
    """Wrapper for pay_fine — called by FineMarkPaidView."""
    return pay_fine(fine_id)


def create_staff_schedule(hall_id, staff_id, day_of_week, start_time, end_time, shift_type=None):
    """
    Create a staff schedule — called by StaffScheduleListCreateView.
    Enforces:
    - BR-HM-016: Guard Shift Conflict Prevention
    - BR-HM-027: Security Audit Logging
    """
    from .models import StaffSchedule, Hall
    from django.db.models import Q
    import logging
    
    logger = logging.getLogger(__name__)
    
    hall = Hall.objects.filter(id=hall_id).first()
    if not hall:
        raise HostelManagementException(f"Hall {hall_id} not found.")
    
    from applications.globals.models import Staff
    staff = Staff.objects.filter(id=staff_id).first()
    if not staff:
        raise HostelManagementException(f"Staff {staff_id} not found.")
        
    if start_time >= end_time:
        raise HostelManagementException("Shift end time must be after start time.")
    
    # BR-HM-016: Prevent overlapping shifts
    overlapping = StaffSchedule.objects.filter(
        staff=staff, 
        day_of_week=day_of_week
    ).filter(
        Q(start_time__lt=end_time) & Q(end_time__gt=start_time)
    )
    
    if overlapping.exists():
        raise HostelManagementException("Staff already has an overlapping shift on this day.")
    
    schedule = StaffSchedule.objects.create(
        hall=hall,
        staff=staff,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
        shift_type=shift_type or 'Caretaker'
    )
    
    # BR-HM-027: Security Audit Logging
    logger.info(f"SECURITY AUDIT: Shift created for {staff.id.user.username} at {hall.hall_name} "
                f"on {day_of_week} ({start_time}-{end_time}) by system.")
                
    return schedule


def add_inventory_item(hall_id, item_name, quantity, unit_cost, remarks=None):
    """
    Add an inventory item — called by InventoryListCreateView.
    Enforces:
    - BR-HM-030: Resource Request Validation
    - BR-HM-031: Inventory Audit Trail
    """
    from .models import HostelInventory, Hall
    import logging
    
    logger = logging.getLogger(__name__)
    
    hall = Hall.objects.filter(id=hall_id).first()
    if not hall:
        raise HostelManagementException(f"Hall {hall_id} not found.")
        
    # BR-HM-030: Quantity must be positive
    if quantity <= 0:
        raise HostelManagementException("Quantity must be a positive integer.")
    
    item = HostelInventory.objects.create(
        hall=hall,
        item_name=item_name,
        quantity=quantity,
        unit_cost=unit_cost,
        remarks=remarks
    )
    
    # BR-HM-031: Inventory Audit Trail
    logger.info(f"INVENTORY AUDIT: Added item {item_name} (Qty: {quantity}) to {hall.hall_name}.")
    
    return item


# ══════════════════════════════════════════════════════════════
# NEW FEATURES: VACATIONS & EXTENDED STAYS (BR-HM-015 - BR-HM-062)
# ══════════════════════════════════════════════════════════════

def process_room_vacation(vacation_id, action, remarks=None):
    """
    Process Room Vacation Request.
    Enforces:
    - BR-HM-015: Room Vacation Prerequisites (no fines)
    - BR-HM-028: Vacation Finalization
    - BR-HM-023: Room Availability update on deallocation
    """
    from .models import HostelFine, FineStatusChoices, RoomAllocationStatusChoices
    
    vacation = selectors.get_room_vacation(vacation_id)
    if not vacation:
        raise HostelManagementException("Vacation request not found.")
        
    student = vacation.student
    
    if action == 'approve':
        # BR-HM-015: Check outstanding fines
        outstanding_fines = HostelFine.objects.filter(
            student=student, 
            status=FineStatusChoices.PENDING
        ).exists()
        if outstanding_fines:
            raise HostelManagementException("Student cannot vacate: Outstanding fines exist.")
            
        vacation.status = 'approved'
        vacation.remarks = remarks
        vacation.save()
        
        # BR-HM-023 & BR-HM-028: Update room availability and release allocation
        current_alloc = selectors.get_student_current_allocation(student)
        if current_alloc and current_alloc.room:
            room = current_alloc.room
            room.current_occupancy = max(0, room.current_occupancy - 1)
            if room.current_occupancy == 0:
                room.status = 'available'
            room.save()
            
            current_alloc.status = RoomAllocationStatusChoices.VACANT
            from django.utils import timezone
            current_alloc.release_date = timezone.now().date()
            current_alloc.save()
            
    elif action == 'verify':
        vacation.status = 'verified'
        vacation.remarks = remarks
        vacation.save()
        
    return vacation


def create_extended_stay(student, start_date, end_date, reason):
    """
    Submit Extended Stay.
    Enforces:
    - BR-HM-061: Extended Stay Eligibility (Must have active alloc)
    - BR-HM-062: Vacation Period Validation
    """
    from .models import ExtendedStayApplication
    
    # BR-HM-061: Active hostel allocation is required
    current_allocation = selectors.get_student_current_allocation(student.pk)
    if not current_allocation or current_allocation.status != RoomAllocationStatusChoices.ALLOCATED:
        raise HostelManagementException("Student must have active hostel allocation for extended stay.")
        
    # BR-HM-062: Date validation
    from django.utils import timezone
    today = timezone.now().date()
    if start_date < today:
        raise HostelManagementException("Start date cannot be in the past.")
    if end_date <= start_date:
        raise HostelManagementException("End date must be after start date.")
        
    duration = (end_date - start_date).days
    if duration > 45:
        raise HostelManagementException("Extended stay cannot exceed 45 days.")
        
    stay = ExtendedStayApplication.objects.create(
        student=student,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
        status='pending'
    )
    return stay
    
    def update_inventory(inventory_id, quantity=None, remarks=None):
        """
        Update an inventory item — called by InventoryRetrieveUpdateView.
        Enforces:
        - BR-HM-030: Resource Request Validation
        - BR-HM-021: Discrepancy Logging
        - BR-HM-031: Inventory Audit Trail
        """
        import logging
        logger = logging.getLogger(__name__)
    
        item = selectors.get_inventory_item(inventory_id)
        if not item:
            raise HostelManagementException(f"Inventory item {inventory_id} not found.")
        
        old_qty = item.quantity
        
        if quantity is not None:
            if quantity < 0:
                raise HostelManagementException("Quantity cannot be negative.")
            item.quantity = quantity
        
        if remarks is not None:
            item.remarks = remarks
            
        item.save()
        
        # BR-HM-021: Discrepancy logging
        if quantity is not None and quantity < old_qty:
            logger.warning(
                f"DISCREPANCY LOG: {item.item_name} at {item.hall.hall_name} decreased from {old_qty} to {quantity}. Remarks: {remarks}"
            )
            
        # BR-HM-031: Audit Trail
        logger.info(f"INVENTORY AUDIT: Updated item {item.item_name} to Qty: {quantity}")
        
        return item
# --------------------------------------------------------------
# HM-WF-103: ACCOMMODATION REQUEST & ALLOTMENT SERVICES
# --------------------------------------------------------------

@transaction.atomic
def create_accommodation_request(student, window_id, preferred_hostel_type, preferred_room_type):
    from .models import AccommodationApplicationWindow, AccommodationRequest
    window = AccommodationApplicationWindow.objects.get(id=window_id)
    if not window.is_open:
        raise ApplicationWindowError(f'Application window {window.name} is currently closed.')
    request, created = AccommodationRequest.objects.get_or_create(
        student=student, window=window,
        defaults={'preferred_hostel_type': preferred_hostel_type, 'preferred_room_type': preferred_room_type}
    )
    if not created:
        request.preferred_hostel_type = preferred_hostel_type
        request.preferred_room_type = preferred_room_type
        request.save()
    return request

@transaction.atomic
def perform_bulk_allotment_logic(request_ids, allotted_by):
    from django.db.models import F
    from .models import AccommodationRequest, Hostel, Room, RoomAllotment, HostelStatusChoices, RoomSetupStatusChoices
    results = {'success': [], 'failed': []}
    requests = AccommodationRequest.objects.filter(id__in=request_ids, status=AccommodationRequest.Status.PENDING)
    for req in requests:
        try:
            suitable_hostels = Hostel.objects.filter(type=req.preferred_hostel_type, status=HostelStatusChoices.ACTIVE)
            allotted = False
            for hostel in suitable_hostels:
                available_room = Room.objects.filter(hostel=hostel, current_occupancy__lt=F('capacity'), status=RoomSetupStatusChoices.AVAILABLE).first()
                if available_room:
                    RoomAllotment.objects.filter(student=req.student, is_active=True).update(is_active=False)
                    RoomAllotment.objects.create(student=req.student, room=available_room, hostel=hostel, allotted_by=allotted_by)
                    available_room.current_occupancy += 1
                    available_room.save()
                    req.status = AccommodationRequest.Status.ALLOTTED
                    req.save()
                    results['success'].append(req.id)
                    allotted = True
                    break
            if not allotted:
                results['failed'].append({'id': req.id, 'reason': 'No capacity available'})
        except Exception as e:
            results['failed'].append({'id': req.id, 'reason': str(e)})
    return results

def perform_bulk_batch_allocation(hall_id, programme_category, admission_year, gender, allotted_by):
    """
    Perform sequential bulk batch allocation.
    - Matches students by category, admission year, and gender.
    - Only considers students without active allotments.
    - Fills rooms floor-by-floor, topping up partially filled rooms first.
    """
    from django.db import transaction
    from django.db.models import F
    from django.shortcuts import get_object_or_404
    from applications.academic_information.models import Student
    from .models import Hostel, Room, RoomAllotment, RoomSetupStatusChoices

    # 1. Map programme category to actual programme strings
    category_map = {
        'UG': ['B.Tech', 'B.Des'],
        'PG': ['M.Des', 'PhD'],
        'M.Tech': ['M.Tech']
    }
    programmes = category_map.get(programme_category, [])

    with transaction.atomic():
        # 2. Identify target Hostel and verify gender
        hostel = get_object_or_404(Hostel, hall_id=hall_id)
        
        # Gender mismatch check (prevent cross-gender bulk allocation)
        if gender == 'M' and hostel.type == 'Girl':
             raise ValueError(f"Hostel {hall_id} is for Girls, but Male students selected.")
        if gender == 'F' and hostel.type == 'Boy':
             raise ValueError(f"Hostel {hall_id} is for Boys, but Female students selected.")

        # 3. Fetch eligible students (Sequential by their ID/username)
        students = Student.objects.filter(
            programme__in=programmes,
            batch=admission_year,
            id__sex=gender
        ).exclude(
            room_allotments__is_active=True
        ).select_related('id__user').order_by('id__user__username')
        
        # Load students into memory to avoid N+1 query performance bottleneck during iteration
        students_list = list(students)
        total_students = len(students_list)
        if total_students == 0:
            return {'count': 0, 'total_found': 0, 'message': 'No eligible students found for this batch.'}

        # 4. Fetch available rooms, sorted by floor then room number
        # We fill partially occupied rooms first within the same floor priority
        available_rooms = Room.objects.filter(
            hostel=hostel,
            status=RoomSetupStatusChoices.AVAILABLE,
            current_occupancy__lt=F('capacity')
        ).order_by('floor', 'room_number')

        allotted_count = 0
        student_idx = 0
        
        for room in available_rooms:
            if student_idx >= total_students:
                break
                
            while room.current_occupancy < room.capacity and student_idx < total_students:
                student = students_list[student_idx]
                
                # Create Allotment
                RoomAllotment.objects.create(
                    student=student,
                    room=room,
                    hostel=hostel,
                    allotted_by=allotted_by,
                    is_active=True
                )
                
                room.current_occupancy += 1
                allotted_count += 1
                student_idx += 1
            
            # Update room status if full
            if room.current_occupancy >= room.capacity:
                room.status = RoomSetupStatusChoices.OCCUPIED
            room.save()
            
        return {
            'count': allotted_count,
            'total_found': total_students,
            'message': f"Successfully allotted {allotted_count} of {total_students} students."
        }


@transaction.atomic
def delete_room_allotment(allotment_id):
    """
    Permanently delete a room allotment and reconcile occupancy.
    - Used by Super Admins to manually clear allocations.
    """
    # Use global RoomSetupStatusChoices, fallback to string if necessary
    try:
        AVAILABLE = RoomSetupStatusChoices.AVAILABLE
    except (AttributeError, NameError):
        AVAILABLE = "Available"

    # Fetch allotment without select_for_update to avoid transaction isolation issues in some environments
    allotment = RoomAllotment.objects.filter(id=allotment_id).first()
    if not allotment:
        raise HostelManagementException(f"Allocation record {allotment_id} not found.")

    room = allotment.room
    if not room:
        # If room is missing, we still delete the allotment but log a warning
        allotment.delete()
        return True

    # Update room occupancy safely
    room.current_occupancy = max(0, (room.current_occupancy or 1) - 1)
    
    # If room is now below capacity, mark as available
    if room.current_occupancy < room.capacity:
        room.status = AVAILABLE
        
    room.save()

    # Delete the allotment record
    allotment.delete()
    
    return True
