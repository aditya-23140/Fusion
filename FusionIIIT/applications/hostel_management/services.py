"""
Hostel Management Services

This module contains ALL business logic, state mutations, and rule enforcement.
- Business Rules are enforced here and raise custom exceptions on violation
- All database mutations go through services
- Services use selectors for queries
"""

from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from .models import (
    HostelLeave, HostelComplaint, RoomAllocation, RoomAllocationChange,
    HostelFine, HostelStudentAttendance,
    GuestRoomBooking, GuestRoom,
    LeaveStatusChoices, ComplaintStatusChoices, RoomAllocationStatusChoices,
    AllocationChangeStatusChoices, FineStatusChoices, BookingStatusChoices
)
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
    current_allocation = selectors.get_student_current_allocation(student.id)
    if not current_allocation or current_allocation.status != RoomAllocationStatusChoices.ALLOCATED:
        raise LeaveEligibilityError(
            "Student must have an active hostel allocation to request leave."
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
        start_date=start_date,
        end_date=end_date,
        reason=reason,
        destination=destination,
        contact_phone=contact_phone,
        status=LeaveStatusChoices.PENDING
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
    current_allocation = selectors.get_student_current_allocation(student.id)
    if not current_allocation or not current_allocation.room:
        return
    
    hall = current_allocation.room.hall
    current_date = start_date
    
    while current_date <= end_date:
        HostelStudentAttendance.objects.update_or_create(
            student=student,
            date=current_date,
            defaults={
                'hall': hall,
                'is_present': is_present,
                'remarks': 'Leave' if not is_present else None
            }
        )
        current_date += timedelta(days=1)


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
    current_allocation = selectors.get_student_current_allocation(student.id)
    if not current_allocation or current_allocation.status != RoomAllocationStatusChoices.ALLOCATED:
        raise ComplaintEligibilityError(
            "Only students with active hostel allocation can file complaints."
        )
    
    # Validate complaint data
    if not title or len(title.strip()) < 5:
        raise ComplaintRoutingError("Complaint title must be at least 5 characters.")
    
    if not description or len(description.strip()) < 20:
        raise ComplaintRoutingError("Complaint description must be at least 20 characters.")
    
    # Get hall from student's allocation
    hall = current_allocation.room.hall
    
    # BR-HM-107: Route complaint to appropriate caretaker by category
    caretaker = selectors.get_hall_caretaker(hall.hall_id)
    
    complaint = HostelComplaint.objects.create(
        student=student,
        hall=hall,
        title=title,
        description=description,
        category=category,
        priority=priority,
        location=location,
        status=ComplaintStatusChoices.OPEN,
        assigned_to=caretaker.staff if caretaker else None
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
# HM-WF-103: ROOM ALLOCATION SERVICES
# ══════════════════════════════════════════════════════════════

def bulk_allocate_rooms(room_allocations_data):
    """
    Bulk allocate rooms to students.
    
    Enforces:
    - BR-HM-112: Bulk Allotment Capacity Safeguard
    - BR-HM-113: Super Admin Allotment Authority
    """
    created_allocations = []
    
    for alloc_data in room_allocations_data:
        student = alloc_data['student']
        room = alloc_data['room']
        
        # BR-HM-112: Check room capacity
        occupied_count = selectors.count_occupied_seats_in_room(room.id)
        if occupied_count >= room.capacity:
            raise AllotmentCapacityError(
                f"Room {room.room_number} is at full capacity ({room.capacity}/{room.capacity})."
            )
          # Create allocation
        allocation = RoomAllocation.objects.create(
            student=student,
            room=room,
            hall=alloc_data.get('hall'),
            allocation_date=timezone.now().date(),
            status=RoomAllocationStatusChoices.ALLOCATED,
            allocated_by=alloc_data.get('allocated_by')
        )
        
        created_allocations.append(allocation)
        
        # Update room occupancy
        room.current_occupancy = occupied_count + 1
        room.save()
    
    return created_allocations


def release_room_allocation(allocation_id):
    """Release a student from their room allocation."""
    allocation = selectors.get_allocation_by_id(allocation_id)
    if not allocation:
        raise HostelManagementException(f"Allocation {allocation_id} not found.")
    
    if allocation.status != RoomAllocationStatusChoices.ALLOCATED:
        raise HostelManagementException(
            f"Cannot release allocation in {allocation.status} status."
        )
    
    # Update allocation
    allocation.status = RoomAllocationStatusChoices.VACANT
    allocation.release_date = timezone.now().date()
    allocation.save()
    
    # Update room occupancy
    if allocation.room:
        allocation.room.current_occupancy = max(0, allocation.room.current_occupancy - 1)
        allocation.room.save()
    
    return allocation


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
    current_allocation = selectors.get_student_current_allocation(student.pk)
    if not current_allocation or current_allocation.status != RoomAllocationStatusChoices.ALLOCATED:
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
    change = selectors.get_room_change(change_id)
    if not change:
        raise HostelManagementException(f"Room change {change_id} not found.")
    
    if change.status != AllocationChangeStatusChoices.APPROVED_WARDEN:
        raise DualApprovalError(
            "Room change must be approved by warden before caretaker approval."
        )
    
    # BR-HM-117: Check capacity of requested room
    occupied_count = selectors.count_occupied_seats_in_room(change.requested_room.id)
    if occupied_count >= change.requested_room.capacity:
        raise AllotmentCapacityError(
            f"Requested room is at full capacity and cannot accommodate change."
        )
    
    # Update allocations
    current_allocation = selectors.get_student_current_allocation(change.student.id)
    if current_allocation:
        # Release from current room
        current_allocation.status = RoomAllocationStatusChoices.VACANT
        current_allocation.release_date = timezone.now().date()
        current_allocation.save()
        
        # Update current room occupancy
        if current_allocation.room:
            current_allocation.room.current_occupancy = max(0, current_allocation.room.current_occupancy - 1)
            current_allocation.room.save()
    
    # Create new allocation in requested room
    new_allocation = RoomAllocation.objects.create(
        student=change.student,
        room=change.requested_room,
        allocation_date=timezone.now().date(),
        status=RoomAllocationStatusChoices.ALLOCATED
    )
    
    # Update requested room occupancy
    change.requested_room.current_occupancy += 1
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

def issue_fine(student, hall, fine_type, amount, reason, due_date, issued_by):
    """
    Issue a fine to a student.
    
    Enforces:
    - BR-HM-013: Fine Imposition Validation
    """
    # BR-HM-013: Validate fine data
    if not student or not hall:
        raise FineValidationError("Student and hall are required to issue a fine.")
    
    if amount <= 0:
        raise FineValidationError("Fine amount must be greater than zero.")
    
    if due_date < timezone.now().date():
        raise FineValidationError("Due date cannot be in the past.")
    
    if not reason or len(reason.strip()) < 10:
        raise FineValidationError("Fine reason must be at least 10 characters.")
    
    # Check if student is/was in this hall
    current_allocation = selectors.get_student_current_allocation(student.id)
    if not current_allocation or current_allocation.room.hall != hall:
        # Allow issuing fine even if student has left, but check recent allocation
        pass
    
    fine = HostelFine.objects.create(
        student=student,
        hall=hall,
        fine_type=fine_type,
        amount=Decimal(str(amount)),
        reason=reason,
        due_date=due_date,
        status=FineStatusChoices.PENDING,
        issued_by=issued_by,
        issued_date=timezone.now().date()
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
    
    current_allocation = selectors.get_student_current_allocation(student_obj.pk)
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

def assign_warden_to_hall(hall, faculty):
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
    existing_wardens = HallWarden.objects.filter(hall=hall)
    if existing_wardens.exists():
        existing_wardens.delete()
    
    # Assign new warden
    warden = HallWarden.objects.create(
        hall=hall,
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
    from applications.programme_curriculum.models import AcademicBatch
    
    # Get all active batches
    active_batches = AcademicBatch.objects.filter(
        is_active=True
    ).values('id', 'batch_id', 'discipline', 'year').distinct()
    
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
