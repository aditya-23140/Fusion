"""
Serializers - DRF serializers with field-level validation only.

This module contains all DRF serializers for hostel management.
NO business logic here - only field-level validate_<fieldname> methods.
"""

from rest_framework import serializers
import re

from ..models import (
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
)


# ══════════════════════════════════════════════════════════════
# HALL SERIALIZERS
# ══════════════════════════════════════════════════════════════

class HallSerializer(serializers.ModelSerializer):
    vacant_seats = serializers.SerializerMethodField()

    class Meta:
        model = Hall
        fields = ['id', 'hall_id', 'hall_name', 'max_accomodation', 'number_students', 'vacant_seats', 'assigned_batch', 'type_of_seater']
        read_only_fields = ['id', 'number_students']

    def get_vacant_seats(self, obj):
        return obj.max_accomodation - obj.number_students


class HallCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hall
        fields = ['hall_id', 'hall_name', 'max_accomodation', 'type_of_seater', 'assigned_batch']


# ══════════════════════════════════════════════════════════════
# CARETAKER & WARDEN SERIALIZERS
# ══════════════════════════════════════════════════════════════

class AssignCaretakerSerializer(serializers.Serializer):
    hall_id = serializers.CharField(max_length=10)
    caretaker_username = serializers.CharField(max_length=100)


class AssignWardenSerializer(serializers.Serializer):
    hall_id = serializers.CharField(max_length=10)
    warden_username = serializers.CharField(max_length=100)


class AssignBatchSerializer(serializers.Serializer):
    hall_id = serializers.CharField(max_length=10)
    batch = serializers.CharField(max_length=50)


# ══════════════════════════════════════════════════════════════
# GUEST ROOM BOOKING SERIALIZERS
# ══════════════════════════════════════════════════════════════

class GuestRoomBookingSerializer(serializers.ModelSerializer):
    hall_name = serializers.CharField(source='hall.hall_name', read_only=True)
    intender_username = serializers.CharField(source='intender.username', read_only=True)

    class Meta:
        model = GuestRoomBooking
        fields = [
            'id', 'hall', 'hall_name', 'intender', 'intender_username',
            'guest_name', 'guest_phone', 'guest_email', 'guest_address',
            'rooms_required', 'guest_room_id', 'total_guest', 'purpose',
            'arrival_date', 'arrival_time', 'departure_date', 'departure_time',
            'status', 'booking_date', 'nationality', 'room_type'
        ]
        read_only_fields = ['id', 'intender', 'status', 'booking_date', 'guest_room_id']


class GuestRoomBookingCreateSerializer(serializers.Serializer):
    hall_id = serializers.IntegerField()
    guest_name = serializers.CharField(max_length=255)
    guest_phone = serializers.CharField(max_length=255)
    guest_email = serializers.EmailField(required=False, allow_blank=True)
    guest_address = serializers.CharField(required=False, allow_blank=True)
    rooms_required = serializers.IntegerField(min_value=1)
    total_guest = serializers.IntegerField(min_value=1)
    purpose = serializers.CharField()
    arrival_date = serializers.DateField()
    arrival_time = serializers.TimeField()
    departure_date = serializers.DateField()
    departure_time = serializers.TimeField()
    nationality = serializers.CharField(max_length=255, required=False, allow_blank=True)
    room_type = serializers.ChoiceField(choices=['single', 'double', 'triple'])

    def validate(self, data):
        if data['departure_date'] < data['arrival_date']:
            raise serializers.ValidationError("Departure date must be after arrival date.")
        return data


class ApproveBookingSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField()
    guest_room_id = serializers.IntegerField()


# ══════════════════════════════════════════════════════════════
# GUEST ROOM SERIALIZERS
# ══════════════════════════════════════════════════════════════

class GuestRoomSerializer(serializers.ModelSerializer):
    hall_name = serializers.CharField(source='hall.hall_name', read_only=True)

    class Meta:
        model = GuestRoom
        fields = ['id', 'hall', 'hall_name', 'room', 'occupied_till', 'vacant', 'room_type']
        read_only_fields = ['id']


# ══════════════════════════════════════════════════════════════
# STAFF SCHEDULE SERIALIZERS
# ══════════════════════════════════════════════════════════════

class StaffScheduleSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source='staff_id.id.user.username', read_only=True)
    hall_id = serializers.CharField(source='hall.hall_id', read_only=True)

    class Meta:
        model = StaffSchedule
        fields = ['id', 'hall', 'hall_id', 'staff_id', 'staff_name', 'staff_type', 'day', 'start_time', 'end_time']
        read_only_fields = ['id']


class StaffScheduleCreateSerializer(serializers.Serializer):
    hall_id = serializers.CharField(max_length=10)
    staff_id = serializers.IntegerField()
    staff_type = serializers.CharField(max_length=100)
    day = serializers.ChoiceField(choices=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'])
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()

    def validate(self, data):
        if data['end_time'] <= data['start_time']:
            raise serializers.ValidationError("End time must be after start time.")
        return data


# ══════════════════════════════════════════════════════════════
# NOTICE BOARD SERIALIZERS
# ══════════════════════════════════════════════════════════════

class NoticeBoardSerializer(serializers.ModelSerializer):
    posted_by_name = serializers.CharField(source='posted_by.user.username', read_only=True)
    hall_name = serializers.CharField(source='hall.hall_name', read_only=True)

    class Meta:
        model = HostelNoticeBoard
        fields = ['id', 'hall', 'hall_name', 'posted_by', 'posted_by_name', 'head_line', 'content', 'description']
        read_only_fields = ['id', 'posted_by']


class NoticeCreateSerializer(serializers.Serializer):
    hall_id = serializers.IntegerField()
    head_line = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True)
    content = serializers.FileField(required=False, allow_null=True)


# ══════════════════════════════════════════════════════════════
# ATTENDANCE SERIALIZERS
# ══════════════════════════════════════════════════════════════

class StudentAttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student_id.id.user.username', read_only=True)
    hall_name = serializers.CharField(source='hall.hall_name', read_only=True)

    class Meta:
        model = HostelStudentAttendence
        fields = ['id', 'hall', 'hall_name', 'student_id', 'student_name', 'date', 'present']
        read_only_fields = ['id']


class MarkAttendanceSerializer(serializers.Serializer):
    student_id = serializers.CharField(max_length=20)
    date = serializers.DateField()


# ══════════════════════════════════════════════════════════════
# ROOM SERIALIZERS
# ══════════════════════════════════════════════════════════════

class HallRoomSerializer(serializers.ModelSerializer):
    hall_name = serializers.CharField(source='hall.hall_name', read_only=True)

    class Meta:
        model = HallRoom
        fields = ['id', 'hall', 'hall_name', 'room_no', 'block_no', 'room_cap', 'room_occupied']
        read_only_fields = ['id']


class ChangeRoomSerializer(serializers.Serializer):
    student_id = serializers.CharField(max_length=20)
    new_room_no = serializers.CharField(max_length=4)
    new_hall_no = serializers.CharField(max_length=1)


# ══════════════════════════════════════════════════════════════
# LEAVE SERIALIZERS
# ══════════════════════════════════════════════════════════════

class HostelLeaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = HostelLeave
        fields = ['id', 'student_name', 'roll_num', 'reason', 'phone_number', 'start_date', 'end_date', 'status', 'remark', 'file_upload']
        read_only_fields = ['id', 'status']


class LeaveCreateSerializer(serializers.Serializer):
    student_name = serializers.CharField(max_length=100)
    roll_num = serializers.CharField(max_length=20)
    reason = serializers.CharField()
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    file_upload = serializers.FileField(required=False, allow_null=True)

    def validate(self, data):
        if data['end_date'] < data['start_date']:
            raise serializers.ValidationError("End date must be after or equal to start date.")
        return data


class UpdateLeaveStatusSerializer(serializers.Serializer):
    leave_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=['Approved', 'Rejected'])
    remark = serializers.CharField(required=False, allow_blank=True)


# ══════════════════════════════════════════════════════════════
# COMPLAINT SERIALIZERS
# ══════════════════════════════════════════════════════════════

class HostelComplaintSerializer(serializers.ModelSerializer):
    class Meta:
        model = HostelComplaint
        fields = ['id', 'hall_name', 'student_name', 'roll_number', 'description', 'contact_number']
        read_only_fields = ['id']


class ComplaintCreateSerializer(serializers.Serializer):
    hall_name = serializers.CharField(max_length=100)
    student_name = serializers.CharField(max_length=100)
    roll_number = serializers.CharField(max_length=20)
    description = serializers.CharField()
    contact_number = serializers.CharField(max_length=15)

    def validate_contact_number(self, value):
        if not re.match(r'^\+?1?\d{9,15}$', value):
            raise serializers.ValidationError("Enter a valid contact number.")
        return value


# ══════════════════════════════════════════════════════════════
# FINE SERIALIZERS
# ══════════════════════════════════════════════════════════════

class HostelFineSerializer(serializers.ModelSerializer):
    student_roll_no = serializers.CharField(source='student.id.id', read_only=True)
    hall_name = serializers.CharField(source='hall.hall_name', read_only=True)

    class Meta:
        model = HostelFine
        fields = ['fine_id', 'student', 'student_roll_no', 'hall', 'hall_name', 'student_name', 'amount', 'status', 'reason']
        read_only_fields = ['fine_id']


class ImposeFineSerializer(serializers.Serializer):
    student_id = serializers.CharField(max_length=20)
    student_name = serializers.CharField(max_length=100)
    hall_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    reason = serializers.CharField()


class UpdateFineSerializer(serializers.Serializer):
    fine_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False)
    status = serializers.ChoiceField(choices=['Pending', 'Paid'], required=False)
    reason = serializers.CharField(required=False)


# ══════════════════════════════════════════════════════════════
# INVENTORY SERIALIZERS
# ══════════════════════════════════════════════════════════════

class HostelInventorySerializer(serializers.ModelSerializer):
    hall_name = serializers.CharField(source='hall.hall_name', read_only=True)

    class Meta:
        model = HostelInventory
        fields = ['inventory_id', 'hall', 'hall_name', 'inventory_name', 'cost', 'quantity']
        read_only_fields = ['inventory_id']


class InventoryCreateSerializer(serializers.Serializer):
    hall_id = serializers.IntegerField()
    inventory_name = serializers.CharField(max_length=100)
    cost = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    quantity = serializers.IntegerField(min_value=0)


# ══════════════════════════════════════════════════════════════
# WORKER REPORT SERIALIZERS
# ══════════════════════════════════════════════════════════════

class WorkerReportSerializer(serializers.ModelSerializer):
    hall_name = serializers.CharField(source='hall.hall_name', read_only=True)

    class Meta:
        model = WorkerReport
        fields = ['id', 'worker_id', 'hall', 'hall_name', 'worker_name', 'year', 'month', 'absent', 'total_day', 'remark']
        read_only_fields = ['id']


# ══════════════════════════════════════════════════════════════
# HISTORY SERIALIZERS
# ══════════════════════════════════════════════════════════════

class TransactionHistorySerializer(serializers.ModelSerializer):
    hall_name = serializers.CharField(source='hall.hall_name', read_only=True)

    class Meta:
        model = HostelTransactionHistory
        fields = ['id', 'hall', 'hall_name', 'change_type', 'previous_value', 'new_value', 'timestamp']
        read_only_fields = ['id', 'timestamp']


class HostelHistorySerializer(serializers.ModelSerializer):
    hall_name = serializers.CharField(source='hall.hall_name', read_only=True)
    caretaker_name = serializers.CharField(source='caretaker.id.user.username', read_only=True)
    warden_name = serializers.CharField(source='warden.id.user.username', read_only=True)

    class Meta:
        model = HostelHistory
        fields = ['id', 'hall', 'hall_name', 'timestamp', 'caretaker', 'caretaker_name', 'batch', 'warden', 'warden_name']
        read_only_fields = ['id', 'timestamp']
