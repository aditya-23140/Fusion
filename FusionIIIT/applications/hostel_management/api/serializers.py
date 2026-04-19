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

from django.db import models
from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
import re

from ..models import (
    HostelLeave,
    HostelComplaint,
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
    ComplaintPriorityChoices,
    FineStatusChoices,
    AccommodationApplicationWindow,
    AccommodationRequest,
    RoomAllotment,
    Hostel,
    Room,
    HostelTypeChoices as HostelOpStatusChoices,
    RoomTypeChoices,
    StaffRoleChoices,
    HostelStaffAssignment,
    HostelAuditLog

)


# ══════════════════════════════════════════════════════════════
# HOSTEL SETUP FOUNDATION SERIALIZERS
# ══════════════════════════════════════════════════════════════

class RoomSetupSerializer(serializers.ModelSerializer):
    """Read-only serializer for Room (new Hostel→Room system)."""
    class Meta:
        model = Room
        fields = [
            'id', 'hostel', 'room_number', 'floor', 'capacity',
            'current_occupancy', 'status'
        ]
        read_only_fields = fields


class HostelSetupSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for Hostel list/retrieve.
    Includes computed fields for active warden and caretaker names,
    and room counts.
    """
    active_warden = serializers.SerializerMethodField()
    active_caretaker = serializers.SerializerMethodField()
    total_rooms = serializers.SerializerMethodField()
    occupied_rooms = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Hostel
        fields = [
            'hall_id', 'name', 'type', 'total_capacity', 'floor_count',
            'room_config_json', 'status', 'created_by', 'created_by_name',
            'created_at', 'updated_at',
            'active_warden', 'active_caretaker', 'total_rooms', 'occupied_rooms'
        ]
        read_only_fields = fields

    def get_active_warden(self, obj):
        assignment = obj.staff_assignments.filter(
            role=StaffRoleChoices.WARDEN, is_active=True
        ).select_related('user').first()
        if assignment:
            return {
                'id': assignment.id,
                'user_id': assignment.user.id,
                'name': assignment.user.get_full_name() or assignment.user.username,
                'email': assignment.user.email,
                'start_date': assignment.start_date,
            }
        return None

    def get_active_caretaker(self, obj):
        assignment = obj.staff_assignments.filter(
            role=StaffRoleChoices.CARETAKER, is_active=True
        ).select_related('user').first()
        if assignment:
            return {
                'id': assignment.id,
                'user_id': assignment.user.id,
                'name': assignment.user.get_full_name() or assignment.user.username,
                'email': assignment.user.email,
                'start_date': assignment.start_date,
            }
        return None

    def get_total_rooms(self, obj):
        return obj.rooms_setup.count()

    def get_occupied_rooms(self, obj):
        return obj.rooms_setup.filter(current_occupancy__gt=0).count()

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None


class HostelCreateSerializer(serializers.ModelSerializer):
    """
    Create serializer for Hostel.

    Validates:
    - No duplicate hostel name
    - Positive total_capacity
    - Valid room_config_json schema
    - BR-HM-025: Config is source of truth
    """
    class Meta:
        model = Hostel
        fields = [
            'hall_id', 'name', 'type', 'total_capacity', 'floor_count', 'room_config_json'
        ]
        extra_kwargs = {
            'hall_id': {'required': True, 'allow_blank': False}
        }

    def validate_name(self, value):
        if not value or len(value.strip()) < 2:
            raise serializers.ValidationError("Hostel name must be at least 2 characters.")
        if Hostel.objects.filter(name__iexact=value.strip()).exists():
            raise serializers.ValidationError(f"A hostel named '{value}' already exists.")
        return value.strip()

    def validate_total_capacity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Total capacity must be greater than 0.")
        return value

    def validate_floor_count(self, value):
        if value <= 0:
            raise serializers.ValidationError("Floor count must be at least 1.")
        return value

    def validate_room_config_json(self, value):
        """Validate room_config_json schema."""
        if not value:
            return value

        if not isinstance(value, dict):
            raise serializers.ValidationError("room_config_json must be a JSON object.")

        floors = value.get('floors')
        if floors is None:
            return value  # Empty config is allowed

        if not isinstance(floors, list):
            raise serializers.ValidationError("'floors' must be a list.")

        for i, floor_cfg in enumerate(floors):
            if not isinstance(floor_cfg, dict):
                raise serializers.ValidationError(f"Floor config at index {i} must be an object.")
            if 'floor' not in floor_cfg:
                raise serializers.ValidationError(f"Floor config at index {i} must have 'floor' field.")
            if 'rooms_per_floor' not in floor_cfg:
                raise serializers.ValidationError(f"Floor config at index {i} must have 'rooms_per_floor' field.")
            if floor_cfg.get('rooms_per_floor', 0) <= 0:
                raise serializers.ValidationError(f"Floor {floor_cfg['floor']}: rooms_per_floor must be positive.")
            if floor_cfg.get('capacity_per_room', 1) <= 0:
                raise serializers.ValidationError(f"Floor {floor_cfg['floor']}: capacity_per_room must be positive.")

        return value


class HostelStatusSerializer(serializers.Serializer):
    """
    Serializer for hostel status transitions.

    Validates transition rules before save:
    - BR-HM-008.a: Block deactivation if hostel has occupied rooms
    - BR-HM-008.b: Block activation if no active Warden OR no active Caretaker
    - BR-HM-019.a: Same as BR-HM-008.b
    """
    status = serializers.ChoiceField(choices=HostelOpStatusChoices.choices)

    def validate_status(self, value):
        hostel = self.context.get('hostel')
        if not hostel:
            return value

        current_status = hostel.status

        # Same status — no-op
        if current_status == value:
            raise serializers.ValidationError(f"Hostel is already in '{value}' status.")

        # BR-HM-008.a: Block deactivation if occupied rooms exist
        if value == HostelOpStatusChoices.INACTIVE:
            occupied_rooms = hostel.rooms_setup.filter(current_occupancy__gt=0).exists()
            if occupied_rooms:
                raise serializers.ValidationError(
                    "Cannot deactivate hostel: there are rooms with current occupants. "
                    "All rooms must be vacated before deactivation."
                )

        # BR-HM-008.b / BR-HM-019.a: Block activation without staff
        if value == HostelOpStatusChoices.ACTIVE:
            has_warden = hostel.staff_assignments.filter(
                role=StaffRoleChoices.WARDEN, is_active=True
            ).exists()
            has_caretaker = hostel.staff_assignments.filter(
                role=StaffRoleChoices.CARETAKER, is_active=True
            ).exists()

            if not has_warden:
                raise serializers.ValidationError(
                    "Cannot activate hostel: no active Warden assigned. "
                    "Assign at least one Warden before activating."
                )
            if not has_caretaker:
                raise serializers.ValidationError(
                    "Cannot activate hostel: no active Caretaker assigned. "
                    "Assign at least one Caretaker before activating."
                )

        return value


class StaffAssignmentSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for staff assignment display.
    """
    user_name = serializers.SerializerMethodField()
    user_email = serializers.EmailField(source='user.email', read_only=True)
    hostel_name = serializers.CharField(source='hostel.name', read_only=True)
    assigned_by_name = serializers.SerializerMethodField()

    class Meta:
        model = HostelStaffAssignment
        fields = [
            'id', 'hostel', 'hostel_name', 'user', 'user_name', 'user_email',
            'role', 'start_date', 'end_date', 'is_active',
            'assigned_by', 'assigned_by_name', 'created_at'
        ]
        read_only_fields = fields

    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    def get_assigned_by_name(self, obj):
        if obj.assigned_by:
            return obj.assigned_by.get_full_name() or obj.assigned_by.username
        return None


class StaffAssignmentCreateSerializer(serializers.Serializer):
    """
    Create serializer for staff assignment.

    Validates:
    - User exists
    - Role is valid
    - BR-HM-019.b: Warns (does not block) if staff has concurrent active assignments
    """
    user_id = serializers.IntegerField()
    role = serializers.ChoiceField(choices=StaffRoleChoices.choices)
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)

    def validate_user_id(self, value):
        from django.contrib.auth.models import User
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError(f"User with ID {value} does not exist.")
        return value

    def validate(self, data):
        from django.contrib.auth.models import User
        user = User.objects.get(id=data['user_id'])

        # BR-HM-019.b: Check concurrent active assignments (warn, don't block)
        concurrent_count = HostelStaffAssignment.objects.filter(
            user=user, is_active=True
        ).count()

        if concurrent_count >= 2:
            data['_warning'] = (
                f"{user.get_full_name() or user.username} already has "
                f"{concurrent_count} active hostel assignment(s). "
                "This assignment will proceed, but please review."
            )

        if data.get('end_date') and data['end_date'] < data['start_date']:
            raise serializers.ValidationError("End date must be after start date.")

        return data


class HostelAuditLogSerializer(serializers.ModelSerializer):
    """Read-only serializer for audit log display."""
    performed_by_name = serializers.SerializerMethodField()
    hostel_name = serializers.CharField(source='hostel.name', read_only=True)

    class Meta:
        model = HostelAuditLog
        fields = [
            'id', 'hostel', 'hostel_name', 'action', 'performed_by',
            'performed_by_name', 'detail_json', 'timestamp'
        ]
        read_only_fields = fields

    def get_performed_by_name(self, obj):
        if obj.performed_by:
            return obj.performed_by.get_full_name() or obj.performed_by.username
        return None



# ══════════════════════════════════════════════════════════════
# LEAVE SERIALIZERS (HM-WF-101)
# ══════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════
# LEAVE SERIALIZERS (HM-WF-101)
# ══════════════════════════════════════════════════════════════

class HostelLeaveSerializer(serializers.ModelSerializer):
    """Read-only serializer for Leave details."""
    student_name = serializers.CharField(source='student.id.user.username', read_only=True)
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
    student_name = serializers.CharField(source='student.id.user.username', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.id.user.username', read_only=True, allow_null=True)
    warden_name = serializers.CharField(source='escalated_to.id.user.username', read_only=True, allow_null=True)
    
    class Meta:
        model = HostelComplaint
        fields = [
            'id', 'student', 'student_name', 'hall', 'category', 'priority',
            'title', 'description', 'location', 'status', 'assigned_to',
            'assigned_to_name', 'resolution_remarks', 'escalated_to_warden',
            'escalated_to', 'warden_name', 'created_at', 'updated_at', 'resolved_at'
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
        fields = ['status', 'resolution_remarks', 'priority']
    
    def validate_resolution_remarks(self, value):
        """Validate resolution remarks if status is RESOLVED."""
        if value and len(value.strip()) < 10:
            raise serializers.ValidationError("Resolution notes must be at least 10 characters.")
        return value


class HostelComplaintEscalateSerializer(serializers.Serializer):
    """Serializer for escalating complaint to warden."""
    reason = serializers.CharField(max_length=500)


# ══════════════════════════════════════════════════════════════
# HM-WF-103: ACCOMMODATION SERIALIZERS
# ══════════════════════════════════════════════════════════════

class AccommodationApplicationWindowSerializer(serializers.ModelSerializer):
    """Serializer for accommodation application windows."""
    is_open = serializers.BooleanField(read_only=True)

    class Meta:
        model = AccommodationApplicationWindow
        fields = ['id', 'name', 'start_date', 'end_date', 'is_active', 'is_open', 'created_at']
        read_only_fields = ['id', 'is_open', 'created_at']


class AccommodationRequestSerializer(serializers.ModelSerializer):
    """Serializer for accommodation requests."""
    student_name = serializers.CharField(source='student.id.user.get_full_name', read_only=True)
    roll_number = serializers.CharField(source='student.id.id', read_only=True)
    window_name = serializers.CharField(source='window.name', read_only=True)

    class Meta:
        model = AccommodationRequest
        fields = [
            'id', 'student', 'student_name', 'roll_number',
            'window', 'window_name', 'preferred_hostel_type',
            'preferred_room_type', 'status', 'submitted_at'
        ]
        read_only_fields = ['id', 'student', 'status', 'submitted_at', 'student_name', 'window_name', 'roll_number']

    def validate(self, data):
        """Ensure student doesn't have multiple requests for the same window."""
        request = self.context.get('request')
        if request and request.method == 'POST':
            student = getattr(request.user, 'student', None)
            if not student:
                raise serializers.ValidationError("Only students can submit requests.")
            
            # This is also enforced by unique_together in Model
            window = data.get('window')
            if AccommodationRequest.objects.filter(student=student, window=window).exists():
                raise serializers.ValidationError("You have already submitted a request for this window.")
        
        return data


class RoomAllotmentSerializer(serializers.ModelSerializer):
    """Serializer for active room allotments."""
    student_id = serializers.CharField(source='student.id.user.username', read_only=True)
    student_name = serializers.CharField(source='student.id.user.get_full_name', read_only=True)
    hostel_name = serializers.CharField(source='hostel.name', read_only=True)
    room_number = serializers.CharField(source='room.room_number', read_only=True)
    room = RoomSetupSerializer(read_only=True)

    class Meta:
        model = RoomAllotment
        fields = [
            'id', 'student', 'student_id', 'student_name', 'room', 'room_number', 'hostel',
            'hostel_name', 'allotted_by', 'allotted_at', 'vacated_at', 'is_active'
        ]
        read_only_fields = fields




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
    student_name = serializers.CharField(source='student.id.user.username', read_only=True)
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
    student_name = serializers.CharField(source='student.id.user.username', read_only=True)
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
            'departure_date',
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
    """
    Serializer for Notice Board.
    Enforces:
    - BR-HM-029: Notice Content Validation
    """
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
        
    def validate_title(self, value):
        if not value or len(value) < 5 or len(value) > 200:
            raise serializers.ValidationError("Title must be between 5 and 200 characters.")
        
        profanity = ['spam', 'abuse', 'fake']
        if any(bad_word in value.lower() for bad_word in profanity):
            raise serializers.ValidationError("Title contains prohibited/profane words.")
        return value
        
    def validate_description(self, value):
        if not value or len(value.strip()) < 20:
            raise serializers.ValidationError("Description must be at least 20 characters long.")
            
        profanity = ['spam', 'abuse', 'fake']
        if any(bad_word in value.lower() for bad_word in profanity):
            raise serializers.ValidationError("Description contains prohibited/profane words.")
        return value


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

from ..models import RoomVacationRequest, ExtendedStayApplication

class RoomVacationRequestSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.id.user.username', read_only=True)
    room_number = serializers.CharField(source='room.room_number', read_only=True)
    hall_name = serializers.CharField(source='hall.hall_name', read_only=True)

    class Meta:
        model = RoomVacationRequest
        fields = [
            'id', 'student', 'student_name', 'room', 'room_number', 'hall', 'hall_name',
            'vacation_date', 'status', 'remarks', 'created_at'
        ]
        read_only_fields = ['student', 'status', 'created_at', 'student_name', 'room_number', 'hall_name']


class ExtendedStayApplicationSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.id.user.username', read_only=True)
    room_number = serializers.CharField(source='room.room_number', read_only=True)
    hall_name = serializers.CharField(source='hall.hall_name', read_only=True)

    class Meta:
        model = ExtendedStayApplication
        fields = [
            'id', 'student', 'student_name', 'room', 'room_number', 'hall', 'hall_name',
            'start_date', 'end_date', 'reason', 'status', 'remarks', 'created_at'
        ]
        read_only_fields = ['student', 'status', 'created_at', 'student_name', 'room_number', 'hall_name']


# ══════════════════════════════════════════════════════════════
# ATTENDANCE SERIALIZERS
# ══════════════════════════════════════════════════════════════

class HostelAttendanceSerializer(serializers.ModelSerializer):
    """Serializer for hostel student attendance."""
    student_name = serializers.CharField(source='student_id.id.user.username', read_only=True)
    roll_number = serializers.CharField(source='student_id.id.user.username', read_only=True)
    
    class Meta:
        model = HostelStudentAttendance
        fields = ['id', 'hall', 'student_id', 'student_name', 'roll_number', 'date', 'present', 'remarks']
        read_only_fields = ['id', 'student_name', 'roll_number']


    def get_total_rooms(self, obj):
        return obj.rooms_setup.count()


class RoomCapacityDashboardSerializer(serializers.ModelSerializer):
    """High-level summary of hostel capacity for Super Admin."""
    occupied_seats = serializers.SerializerMethodField()
    total_rooms = serializers.SerializerMethodField()
    
    class Meta:
        model = Hostel
        fields = [
            'hall_id', 'name', 'type', 'total_capacity', 
            'occupied_seats', 'total_rooms', 'status'
        ]
        
    def get_occupied_seats(self, obj):
        return obj.allotments.filter(is_active=True).count()
        
    def get_total_rooms(self, obj):
        return obj.rooms_setup.count()


class BulkAllotmentSerializer(serializers.Serializer):
    """Serializer for bulk allotment actions."""
    request_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )


class BatchAllocationSerializer(serializers.Serializer):
    """
    Serializer for bulk batch allocation by Super Admin.
    Matches students by category, admission year, and gender.
    """
    PROGRAMME_CATEGORIES = [
        ('UG', 'Undergraduate'),
        ('PG', 'Postgraduate'),
        ('M.Tech', 'M.Tech'),
    ]
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]
    
    programme_category = serializers.ChoiceField(choices=PROGRAMME_CATEGORIES)
    admission_year = serializers.IntegerField()
    gender = serializers.ChoiceField(choices=GENDER_CHOICES)
