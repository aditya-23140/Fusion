"""
Serializers - DRF serializers with field-level validation only.

CRITICAL RULES:
- NO business logic here
- Only field-level validate_<fieldname> methods
- Only I/O serialization and validation
- Use validate_<field>() for field-level validation only
- Custom validators must NOT involve database queries beyond basic existence checks

Supports Workflows:
- HM-WF-101: Leave Management
- HM-WF-102: Complaint Management
- HM-WF-103: Room Allocation
- HM-WF-104: Room Changes
- HM-WF-105: Fine Management
"""

from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
import re

from ..models import (
    Hall,
    HallCaretaker,
    HallWarden,
    HallRoom,
    HostelLeave,
    HostelComplaint,
    RoomAllocation,
    RoomAllocationChange,
    HostelFine,
    StaffSchedule,
    HostelNoticeBoard,
    HostelInventory,
    GuestRoom,
    GuestRoomBooking,
    HostelStudentAttendance,
    LeaveStatusChoices,
    ComplaintStatusChoices,
    ComplaintCategoryChoices,
    FineStatusChoices,
    RoomAllocationStatusChoices,
)


# ══════════════════════════════════════════════════════════════
# HALL SERIALIZERS
# ══════════════════════════════════════════════════════════════

class HallSerializer(serializers.ModelSerializer):
    """Read-only serializer for Hall details."""
    number_of_rooms = serializers.SerializerMethodField()
    number_students = serializers.SerializerMethodField()
    
    class Meta:
        model = Hall
        fields = [
            'id', 'hall_id', 'hall_name', 'max_accomodation',
            'number_students', 'assigned_batch', 'type_of_seater', 'number_of_rooms'
        ]
        read_only_fields = fields
    
    def get_number_of_rooms(self, obj):
        """Get the count of rooms in the hall."""
        # Use cached count if available (from prefetch_related)
        if hasattr(obj, '_prefetched_objects_cache'):
            return len(obj.rooms.all())
        return obj.rooms.count()
    
    def get_number_students(self, obj):
        """Get the count of currently allocated students in the hall.
        
        NOTE: This field is expensive in list views. Consider excluding it
        from RoomAllocationListView serializer if showing halls there.
        """
        # Use cached count if available
        if hasattr(obj, '_allocated_count_cache'):
            return obj._allocated_count_cache
        
        return RoomAllocation.objects.filter(
            hall=obj,
            status=RoomAllocationStatusChoices.ALLOCATED).count()


class HallListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for Hall list views - excludes expensive computations."""
    number_of_rooms = serializers.SerializerMethodField()
    number_students = serializers.SerializerMethodField()
    assigned_batch = serializers.SerializerMethodField()
    
    class Meta:
        model = Hall
        fields = [
            'id', 'hall_id', 'hall_name', 'max_accomodation',
            'number_students', 'assigned_batch', 'type_of_seater', 'number_of_rooms'
        ]
        read_only_fields = fields

    def get_number_of_rooms(self, obj):
        """Get the count of rooms in the hall."""
        if hasattr(obj, '_prefetched_objects_cache'):
            return len(obj.rooms.all())
        return obj.rooms.count()
    
    def get_number_students(self, obj):
        """Get the count of currently allocated students in the hall."""
        # Use cached count if available
        if hasattr(obj, '_allocated_count_cache'):
            return obj._allocated_count_cache
        
        return RoomAllocation.objects.filter(
            hall=obj,
            status=RoomAllocationStatusChoices.ALLOCATED).count()
    def get_assigned_batch(self, obj):
        """Extract batch year from assigned_batch field.
        
        The assigned_batch field stores an AcademicBatch object or its year value.
        This method extracts just the year for display.
        """
        if not obj.assigned_batch:
            return None
        
        # If it's already a string/int, try to extract year
        batch_val = obj.assigned_batch
        
        # If batch_val is a string representation of an object
        if isinstance(batch_val, str):
            # Try to find year pattern (4 digits)
            year_match = re.search(r'\b(20\d{2})\b', batch_val)
            if year_match:
                return int(year_match.group(1))
            # If it looks like it could be a year itself
            try:
                year_int = int(batch_val)
                if 2000 <= year_int <= 2100:
                    return year_int
            except (ValueError, TypeError):
                pass
            return batch_val
        
        # If it's an object with a year attribute
        if hasattr(batch_val, 'year'):
            return batch_val.year
        
        # Try to access year as dict key
        if isinstance(batch_val, dict) and 'year' in batch_val:
            return batch_val['year']
        
        # Return None if we can't extract the year
        return None


class HallCreateUpdateSerializer(serializers.ModelSerializer):
    """Create and update serializer for Hall with validation."""
    
    class Meta:
        model = Hall
        fields = [
            'hall_id', 'hall_name', 'max_accomodation',
            'assigned_batch', 'type_of_seater'
        ]
    
    def validate_hall_id(self, value):
        """Validate hall_id format."""
        if not value or len(value) > 10:
            raise serializers.ValidationError("Hall ID must be between 1 and 10 characters.")
        return value
    
    def validate_max_accomodation(self, value):
        """Validate max_accomodation is positive."""
        if value <= 0:
            raise serializers.ValidationError("Max accommodation must be greater than 0.")
        return value


class HallCaretakerSerializer(serializers.ModelSerializer):
    """Serializer for Hall Caretaker assignment."""
    staff_name = serializers.CharField(source='staff.id.user.username', read_only=True)
    hall_name = serializers.CharField(source='hall.hall_name', read_only=True)
    
    class Meta:
        model = HallCaretaker
        fields = ['id', 'hall', 'staff', 'staff_name', 'hall_name', 'assigned_date', 'is_active']
        read_only_fields = ['id', 'assigned_date', 'staff_name', 'hall_name']


class HallWardenSerializer(serializers.ModelSerializer):
    """Serializer for Hall Warden assignment."""
    faculty_name = serializers.CharField(source='faculty.id.user.username', read_only=True)
    hall_name = serializers.CharField(source='hall.hall_name', read_only=True)
    
    class Meta:
        model = HallWarden
        fields = ['id', 'hall', 'faculty', 'faculty_name', 'hall_name', 'assigned_date', 'is_active']
        read_only_fields = ['id', 'assigned_date', 'faculty_name', 'hall_name']


# ══════════════════════════════════════════════════════════════
# HALL ROOM SERIALIZERS
# ══════════════════════════════════════════════════════════════

class HallRoomSerializer(serializers.ModelSerializer):
    """Serializer for Hall Room details."""
    hall_name = serializers.CharField(source='hall.hall_name', read_only=True)
    
    class Meta:
        model = HallRoom
        fields = [
            'id', 'hall', 'hall_name', 'room_number', 'block_number',
            'room_type', 'capacity', 'current_occupancy', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'hall_name']


class HallRoomCreateUpdateSerializer(serializers.ModelSerializer):
    """Create and update serializer for Hall Room."""
    
    class Meta:
        model = HallRoom
        fields = ['room_number', 'block_number', 'room_type', 'capacity']
    
    def validate_capacity(self, value):
        """Validate capacity is positive."""
        if value <= 0:
            raise serializers.ValidationError("Capacity must be greater than 0.")
        return value
    
    def validate_room_number(self, value):
        """Validate room_number format."""
        if not value or len(value) > 20:
            raise serializers.ValidationError("Room number must be between 1 and 20 characters.")
        return value


# ══════════════════════════════════════════════════════════════
# LEAVE SERIALIZERS (HM-WF-101)
# ══════════════════════════════════════════════════════════════

class HostelLeaveSerializer(serializers.ModelSerializer):
    """Read-only serializer for Leave details."""
    student_name = serializers.CharField(source='student.user.username', read_only=True)
    processed_by_name = serializers.CharField(source='processed_by.id.user.username', read_only=True, allow_null=True)
    
    class Meta:
        model = HostelLeave
        fields = [
            'id', 'student', 'student_name', 'start_date', 'end_date',
            'reason', 'destination', 'contact_phone', 'status', 'remarks',
            'processed_by', 'processed_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = fields


class HostelLeaveCreateSerializer(serializers.ModelSerializer):
    """Create serializer for Leave with field-level validation."""
    
    class Meta:
        model = HostelLeave
        fields = ['start_date', 'end_date', 'reason', 'destination', 'contact_phone', 'file_upload']
    
    def validate_start_date(self, value):
        """Validate start_date is in future."""
        if value < timezone.now().date():
            raise serializers.ValidationError("Start date must be in the future.")
        return value
    
    def validate_end_date(self, value):
        """Validate end_date format."""
        if value < timezone.now().date():
            raise serializers.ValidationError("End date must be in the future.")
        return value
    
    def validate(self, data):
        """Validate start_date <= end_date."""
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError("End date must be after or equal to start date.")
        
        duration = (data['end_date'] - data['start_date']).days
        if duration > 90:
            raise serializers.ValidationError("Leave duration cannot exceed 90 days.")
        
        if not data.get('reason') or len(data['reason'].strip()) < 10:
            raise serializers.ValidationError("Reason must be at least 10 characters long.")
        
        return data


class HostelLeaveApprovalSerializer(serializers.Serializer):
    """Serializer for Leave approval/rejection."""
    status = serializers.ChoiceField(choices=[LeaveStatusChoices.APPROVED, LeaveStatusChoices.REJECTED])
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=500)


# ══════════════════════════════════════════════════════════════
# COMPLAINT SERIALIZERS (HM-WF-102)
# ══════════════════════════════════════════════════════════════

class HostelComplaintSerializer(serializers.ModelSerializer):
    """Read-only serializer for Complaint details."""
    student_name = serializers.CharField(source='student.user.username', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.id.user.username', read_only=True, allow_null=True)
    warden_name = serializers.CharField(source='warden_assigned.id.user.username', read_only=True, allow_null=True)
    
    class Meta:
        model = HostelComplaint
        fields = [
            'id', 'student', 'student_name', 'hall', 'category', 'priority',
            'title', 'description', 'location', 'status', 'assigned_to',
            'assigned_to_name', 'resolution_notes', 'escalated_to_warden',
            'warden_assigned', 'warden_name', 'created_at', 'updated_at', 'resolved_at'
        ]
        read_only_fields = fields


class HostelComplaintCreateSerializer(serializers.ModelSerializer):
    """Create serializer for Complaint with field-level validation."""
    
    class Meta:
        model = HostelComplaint
        fields = ['category', 'priority', 'title', 'description', 'location']
    
    def validate_title(self, value):
        """Validate title length."""
        if not value or len(value) < 5:
            raise serializers.ValidationError("Title must be at least 5 characters.")
        if len(value) > 255:
            raise serializers.ValidationError("Title must not exceed 255 characters.")
        return value
    
    def validate_description(self, value):
        """Validate description length."""
        if not value or len(value.strip()) < 20:
            raise serializers.ValidationError("Description must be at least 20 characters.")
        return value
    
    def validate_category(self, value):
        """Validate category is valid."""
        if value not in dict(ComplaintCategoryChoices.choices):
            raise serializers.ValidationError("Invalid complaint category.")
        return value


class HostelComplaintUpdateSerializer(serializers.ModelSerializer):
    """Update serializer for Complaint status and resolution."""
    
    class Meta:
        model = HostelComplaint
        fields = ['status', 'resolution_notes', 'priority']
    
    def validate_resolution_notes(self, value):
        """Validate resolution notes if status is RESOLVED."""
        if value and len(value.strip()) < 10:
            raise serializers.ValidationError("Resolution notes must be at least 10 characters.")
        return value


class HostelComplaintEscalateSerializer(serializers.Serializer):
    """Serializer for escalating complaint to warden."""
    reason = serializers.CharField(max_length=500)


# ══════════════════════════════════════════════════════════════
# ROOM ALLOCATION SERIALIZERS (HM-WF-103)
# ══════════════════════════════════════════════════════════════

class RoomAllocationSerializer(serializers.ModelSerializer):
    """Read-only serializer for Room Allocation details with optimized queries."""
    student_name = serializers.CharField(source='student.id.user.username', read_only=True)
    room_number = serializers.CharField(source='room.room_number', read_only=True, allow_null=True)
    hall_name = serializers.CharField(source='hall.hall_name', read_only=True, allow_null=True)
    allocated_by_name = serializers.CharField(source='allocated_by.id.user.username', read_only=True, allow_null=True)
    
    class Meta:
        model = RoomAllocation
        fields = [
            'id', 'student', 'student_name', 'room', 'room_number', 'hall', 'hall_name', 'status',
            'allocation_date', 'release_date', 'allocated_by', 'allocated_by_name'
        ]
        read_only_fields = fields


class RoomAllocationCreateSerializer(serializers.ModelSerializer):
    """Create serializer for Room Allocation."""
    
    class Meta:
        model = RoomAllocation
        fields = ['room', 'allocation_date']
    
    def validate_allocation_date(self, value):
        """Validate allocation_date."""
        if value < timezone.now().date():
            raise serializers.ValidationError("Allocation date cannot be in the past.")
        return value


# ══════════════════════════════════════════════════════════════
# ROOM ALLOCATION CHANGE SERIALIZERS (HM-WF-104)
# ══════════════════════════════════════════════════════════════

class RoomAllocationChangeSerializer(serializers.ModelSerializer):
    """Serializer for Room Change - both read and write operations."""
    student_name = serializers.CharField(source='student.user.username', read_only=True)
    current_room_number = serializers.CharField(source='current_room.room_number', read_only=True)
    requested_room_number = serializers.CharField(source='requested_room.room_number', read_only=True)
    warden_name = serializers.CharField(source='approved_by_warden.id.user.username', read_only=True, allow_null=True)
    caretaker_name = serializers.CharField(source='approved_by_caretaker.id.user.username', read_only=True, allow_null=True)
    
    class Meta:
        model = RoomAllocationChange
        fields = [
            'id', 'student', 'student_name', 'current_room', 'current_room_number',
            'requested_room', 'requested_room_number', 'reason', 'status',
            'requested_date', 'effective_date', 'approved_by_warden', 'warden_name',
            'warden_remarks', 'approved_by_caretaker', 'caretaker_name', 'caretaker_remarks',
            'rejection_reason', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'student', 'student_name', 'current_room', 'current_room_number',
            'requested_room_number', 'status', 'requested_date', 'effective_date',
            'approved_by_warden', 'warden_name', 'warden_remarks', 'approved_by_caretaker',
            'caretaker_name', 'caretaker_remarks', 'rejection_reason', 'created_at', 'updated_at'
        ]
    
    def validate_reason(self, value):
        """Validate reason length."""
        if not value or len(value.strip()) < 10:
            raise serializers.ValidationError("Reason must be at least 10 characters.")
        return value


class RoomAllocationChangeApprovalSerializer(serializers.Serializer):
    """Serializer for Room Change approval."""
    approve = serializers.BooleanField()
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=500)
    effective_date = serializers.DateField(required=False)


# ══════════════════════════════════════════════════════════════
# FINE SERIALIZERS (HM-WF-105)
# ══════════════════════════════════════════════════════════════

class HostelFineSerializer(serializers.ModelSerializer):
    """Read-only serializer for Fine details."""
    student_name = serializers.CharField(source='student.user.username', read_only=True)
    issued_by_name = serializers.CharField(source='issued_by.id.user.username', read_only=True, allow_null=True)
    waived_by_name = serializers.CharField(source='waived_by.id.user.username', read_only=True, allow_null=True)
    
    class Meta:
        model = HostelFine
        fields = [
            'id', 'student', 'student_name', 'hall', 'fine_type', 'amount',
            'reason', 'status', 'issued_date', 'due_date', 'paid_date',
            'issued_by', 'issued_by_name', 'waived_by', 'waived_by_name',
            'waive_reason', 'created_at', 'updated_at'
        ]
        read_only_fields = fields


class HostelFineCreateSerializer(serializers.ModelSerializer):
    """Create serializer for Fine with field-level validation."""
    
    class Meta:
        model = HostelFine
        fields = ['fine_type', 'amount', 'reason', 'due_date']
    
    def validate_amount(self, value):
        """Validate amount is positive."""
        if value <= 0:
            raise serializers.ValidationError("Fine amount must be greater than 0.")
        if value > 100000:
            raise serializers.ValidationError("Fine amount exceeds maximum limit.")
        return value
    
    def validate_reason(self, value):
        """Validate reason length."""
        if not value or len(value.strip()) < 10:
            raise serializers.ValidationError("Reason must be at least 10 characters.")
        return value
    
    def validate_due_date(self, value):
        """Validate due_date is in future."""
        if value < timezone.now().date():
            raise serializers.ValidationError("Due date must be in the future.")
        return value


class HostelFinePaymentSerializer(serializers.Serializer):
    """Serializer for marking fine as paid."""
    paid_date = serializers.DateField()
    
    def validate_paid_date(self, value):
        """Validate paid_date is not in future."""
        if value > timezone.now().date():
            raise serializers.ValidationError("Paid date cannot be in the future.")
        return value


class HostelFineWaiverSerializer(serializers.Serializer):
    """Serializer for waiving fine."""
    waive_reason = serializers.CharField(max_length=500)


# ══════════════════════════════════════════════════════════════
# STAFF SCHEDULE SERIALIZERS (HM-WF-107)
# ══════════════════════════════════════════════════════════════

class StaffScheduleSerializer(serializers.ModelSerializer):
    """Serializer for Staff Schedule."""
    hall_name = serializers.CharField(source='hall.hall_name', read_only=True)
    staff_name = serializers.CharField(source='staff.id.user.username', read_only=True)
    
    class Meta:
        model = StaffSchedule
        fields = [
            'id', 'hall', 'hall_name', 'staff', 'staff_name', 'day_of_week',
            'start_time', 'end_time', 'shift_type', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'hall_name', 'staff_name']


# ══════════════════════════════════════════════════════════════
# INVENTORY SERIALIZERS (HM-WF-108)
# ══════════════════════════════════════════════════════════════

class HostelInventorySerializer(serializers.ModelSerializer):
    """Serializer for Hostel Inventory."""
    hall_name = serializers.CharField(source='hall.hall_name', read_only=True)
    
    class Meta:
        model = HostelInventory
        fields = [
            'id', 'hall', 'hall_name', 'item_name', 'quantity', 'unit_cost',
            'remarks', 'last_updated', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'hall_name']


# ══════════════════════════════════════════════════════════════
# GUEST ROOM SERIALIZERS (HM-WF-112)
# ══════════════════════════════════════════════════════════════

class GuestRoomSerializer(serializers.ModelSerializer):
    """Read-only serializer for Guest Room."""
    hall_name = serializers.CharField(source='hall.hall_name', read_only=True)
    
    class Meta:
        model = GuestRoom
        fields = [
            'id', 'hall', 'hall_name', 'room_number', 'room_type',
            'capacity', 'status', 'created_at', 'updated_at'
        ]
        read_only_fields = fields


class GuestRoomBookingSerializer(serializers.ModelSerializer):
    """Read-only serializer for Guest Room Booking."""
    student_name = serializers.CharField(source='student.user.username', read_only=True)
    room_number = serializers.CharField(source='guest_room.room_number', read_only=True, allow_null=True)
    
    class Meta:
        model = GuestRoomBooking
        fields = [
            'id', 'student', 'student_name', 'guest_room', 'room_number',
            'guest_name', 'guest_phone', 'guest_email', 'guest_address',
            'nationality', 'total_guests', 'purpose', 'arrival_date',
            'arrival_time', 'departure_date', 'departure_time', 'rooms_required',
            'room_type', 'status', 'review_remarks', 'created_at',
            'updated_at', 'checked_in_at', 'checked_out_at'
        ]
        read_only_fields = fields


class GuestRoomBookingCreateSerializer(serializers.ModelSerializer):
    """Create serializer for Guest Room Booking."""
    
    class Meta:
        model = GuestRoomBooking
        fields = [
            'guest_name', 'guest_phone', 'guest_email', 'guest_address',
            'nationality', 'total_guests', 'purpose', 'arrival_date',
            'arrival_time', 'departure_date', 'departure_time',
            'rooms_required', 'room_type'
        ]
    
    def validate_guest_phone(self, value):
        """Validate phone format."""
        if not value or len(value) < 10:
            raise serializers.ValidationError("Phone number must be at least 10 characters.")
        return value
    
    def validate_total_guests(self, value):
        """Validate total_guests."""
        if value <= 0:
            raise serializers.ValidationError("Total guests must be greater than 0.")
        if value > 100:
            raise serializers.ValidationError("Total guests cannot exceed 100.")
        return value
    
    def validate(self, data):
        """Validate arrival and departure dates."""
        if data['arrival_date'] < timezone.now().date():
            raise serializers.ValidationError("Arrival date cannot be in the past.")
        if data['departure_date'] <= data['arrival_date']:
            raise serializers.ValidationError("Departure date must be after arrival date.")
        
        duration = (data['departure_date'] - data['arrival_date']).days
        if duration > 30:
            raise serializers.ValidationError("Booking duration cannot exceed 30 days.")
        
        return data


# ...existing code...


# ══════════════════════════════════════════════════════════════
# NOTICE BOARD SERIALIZERS (HM-WF-110)
# ══════════════════════════════════════════════════════════════

class HostelNoticeBoardSerializer(serializers.ModelSerializer):
    """Serializer for Notice Board."""
    hall_name = serializers.CharField(source='hall.hall_name', read_only=True)
    posted_by_name = serializers.CharField(source='posted_by.username', read_only=True)
    
    class Meta:
        model = HostelNoticeBoard
        fields = [
            'id', 'hall', 'hall_name', 'title', 'description', 'content_file',
            'posted_by', 'posted_by_name', 'is_active', 'posted_date',
            'archive_date', 'updated_at'
        ]
        read_only_fields = ['id', 'posted_by', 'posted_date', 'posted_by_name', 'hall_name']


# ══════════════════════════════════════════════════════════════
# MISSING APPROVAL SERIALIZERS
# ══════════════════════════════════════════════════════════════

class RoomVacationRequestVerifySerializer(serializers.Serializer):
    """Serializer for room vacation verification and approval."""
    caretaker_remarks = serializers.CharField(required=False, allow_blank=True, max_length=500)
    approval_remarks = serializers.CharField(required=False, allow_blank=True, max_length=500)


class GuestRoomBookingApprovalSerializer(serializers.Serializer):
    """Serializer for approving/rejecting guest room bookings."""
    review_remarks = serializers.CharField(required=False, allow_blank=True, max_length=500)


class ExtendedStayRequestApprovalSerializer(serializers.Serializer):
    """Serializer for approving/rejecting extended stay requests."""
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=500)
    rejection_reason = serializers.CharField(required=False, allow_blank=True, max_length=500)
