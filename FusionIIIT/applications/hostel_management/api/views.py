"""
API Views - Thin orchestration layer only.

CRITICAL RULES:
- NO business logic here
- NO database queries (.objects) here
- Only call selectors.py for queries
- Only call services.py for business logic
- Only instantiate serializers
- Keep views extremely thin and readable

Supports Workflows:
- HM-WF-101: Leave Management
- HM-WF-102: Complaint Management
- HM-WF-103: Room Allocation
- HM-WF-104: Room Changes
- HM-WF-105: Fine Management
- HM-WF-107: Staff Scheduling
- HM-WF-108: Inventory
- HM-WF-109: Room Vacation
- HM-WF-110: Notice Board
- HM-WF-112: Guest Room Booking
- HM-WF-113: Extended Stay
"""

from datetime import datetime
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, BasePermission
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from applications.globals.models import Staff
from applications.globals.models import Faculty
from applications.hostel_management.models import (
    HostelLeave, HostelComplaint, RoomAllocationChange,
    HostelFine, StaffSchedule, HostelInventory, GuestRoomBooking,
    HostelNoticeBoard, HostelStudentAttendance,
    Hostel, Room, RoomAllotment, HostelStaffAssignment
)
from . import serializers
from .serializers import (
    HostelLeaveSerializer, HostelLeaveCreateSerializer, HostelLeaveApprovalSerializer,
    HostelComplaintSerializer, HostelComplaintUpdateSerializer,
    RoomAllocationChangeSerializer,
    RoomAllocationChangeApprovalSerializer,
    HostelFineSerializer, HostelFinePaymentSerializer, HostelFineWaiverSerializer,
    StaffScheduleSerializer, HostelInventorySerializer,
    GuestRoomBookingSerializer, GuestRoomBookingCreateSerializer, GuestRoomBookingApprovalSerializer,
    HostelNoticeBoardSerializer, HostelAttendanceSerializer
)
from .. import selectors, services
from ..services import (
    HostelManagementException, LeaveEligibilityError, LeaveDateError,
    ComplaintEligibilityError, ComplaintRoutingError, ResolutionRemarksError,
    EscalationAuthorizationError, WardenAuthorityError,
    RoomChangeEligibilityError, DualApprovalError, AllotmentCapacityError,
    FineValidationError, ApplicationWindowError
)


# ══════════════════════════════════════════════════════════════
# PAGINATION & ROLE-BASED PERMISSION CLASSES
# ══════════════════════════════════════════════════════════════

class StandardPagination(PageNumberPagination):
    """Standard pagination: 50 items per page for optimized payload."""
    page_size = 50


class IsStudent(BasePermission):
    """Permission check: student role."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and hasattr(request.user, 'student'))


class IsSuperAdmin(BasePermission):
    """Permission check: super administrator role."""
    def has_permission(self, request, view):
        # Super admin logic: can be customized based on project's user tagging
        return bool(request.user and request.user.is_authenticated and (request.user.is_superuser or request.user.groups.filter(name='Super Admin').exists()))
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 500
    page_query_param = 'page'


class IsSuperAdmin(BasePermission):
    """Permission for Super Admin role: hostel creation, warden/caretaker assignment, batch allocation."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_superuser


class IsWardenOrCaretaker(BasePermission):
    def has_permission(self, request, view):
        return selectors.is_user_warden_or_caretaker(request.user)


class IsWarden(BasePermission):
    def has_permission(self, request, view):
        return selectors.is_user_warden(request.user)


class IsCaretaker(BasePermission):
    """Permission for Caretaker role only."""
    def has_permission(self, request, view):
        return selectors.is_user_caretaker(request.user)


class IsStudent(BasePermission):
    """Permission for Student role."""
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        from applications.academic_information.models import Student
        return Student.objects.filter(id__user=request.user).exists()


# ══════════════════════════════════════════════════════════════
# FACULTY & STAFF LIST VIEWS
# ══════════════════════════════════════════════════════════════



# ══════════════════════════════════════════════════════════════
# COMPLAINT MANAGEMENT VIEWS (HM-WF-102)
# ══════════════════════════════════════════════════════════════


class FacultyListView(generics.ListAPIView):
    """List all faculty members available for warden assignment."""
    permission_classes = [IsSuperAdmin]
    
    def get(self, request, *args, **kwargs):
        """Get all faculty members."""
        try:
            faculty_list = Faculty.objects.all().select_related('id__user')
            
            faculty_data = []
            for faculty in faculty_list:
                user = faculty.id.user if faculty.id else None
                if user:
                    faculty_data.append({
                        'id': user.id,  # Get the actual User primary key
                        'extra_id': faculty.id.id, # Keep extra_id for reference
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'email': user.email,
                    })
            
            return Response(faculty_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class StaffListView(generics.ListAPIView):
    """List all staff members available for caretaker assignment."""
    permission_classes = [IsSuperAdmin]
    
    def get(self, request, *args, **kwargs):
        """Get all staff members."""
        try:
            staff_list = Staff.objects.all().select_related('id__user')
            
            staff_data = []
            for staff_member in staff_list:
                user = staff_member.id.user if staff_member.id else None
                if user:
                    staff_data.append({
                        'id': user.id,  # Get the actual User primary key
                        'extra_id': staff_member.id.id, # Keep extra_id for reference
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'email': user.email,
                    })
            
            return Response(staff_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class RoomRenameView(generics.UpdateAPIView):
    """Rename a room (Warden/Caretaker can rename rooms from sequential to custom names)."""
    permission_classes = [IsWardenOrCaretaker]
    serializer_class = serializers.RoomSetupSerializer

    def get_object(self):
        """Get room by ID."""
        room_id = self.kwargs['pk']
        return get_object_or_404(Room, pk=room_id)

    def patch(self, request, *args, **kwargs):
        """
        Rename room.
        Request body: { "room_number": "A101", "block_number": "A" }
        """
        try:
            room_id = self.kwargs['pk']
            room = get_object_or_404(Room, pk=room_id)
            room_number = request.data.get('room_number')
            floor = request.data.get('floor')
            
            if not room_number:
                return Response(
                    {'error': 'room_number is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            updated_room = services.rename_room_in_hostel(room, room_number, floor)
            
            return Response(
                {'message': 'Room renamed successfully'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# ══════════════════════════════════════════════════════════════
# LEAVE MANAGEMENT VIEWS (HM-WF-101)
# ══════════════════════════════════════════════════════════════

class LeaveListCreateView(generics.ListCreateAPIView):
    """List leaves or submit a new leave request."""
    permission_classes = [IsAuthenticated]
    serializer_class = HostelLeaveSerializer

    def get_queryset(self):
        """Get leaves for authenticated user or all leaves if staff."""
        user = self.request.user
        if user.is_staff:
            return selectors.get_all_leaves()
        return selectors.get_student_leaves(user)

    def get_serializer_class(self):
        """Use writable serializer for POST, read-only for GET."""
        if self.request.method == 'POST':
            return HostelLeaveCreateSerializer
        return HostelLeaveSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            print(f"DEBUG: LeaveRequest validation failed: {serializer.errors}")
        return super().post(request, *args, **kwargs)

    def perform_create(self, serializer):
        """Submit leave request via service."""
        try:
            # Get Student instance from User
            student = selectors.get_student(self.request.user.id)
            if not student:
                print(f"DEBUG: User {self.request.user.username} (ID: {self.request.user.id}) is NOT a student.")
                raise HostelManagementException("Only students can submit leave requests. Please login as a student to test this feature.")

            services.create_leave_request(
                student=student,
                start_date=serializer.validated_data['start_date'],
                end_date=serializer.validated_data['end_date'],
                reason=serializer.validated_data['reason'],
                destination=serializer.validated_data.get('destination'),
                contact_phone=serializer.validated_data.get('contact_phone')
            )
        except (LeaveEligibilityError, LeaveDateError, HostelManagementException) as e:
            print(f"DEBUG: LeaveRequest creation failed: {str(e)}")
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": str(e)})


class LeaveMyListView(generics.ListAPIView):
    """List only the authenticated user's leave requests."""
    permission_classes = [IsAuthenticated]
    serializer_class = HostelLeaveSerializer

    def get_queryset(self):
        return selectors.get_student_leaves(self.request.user)


class LeaveRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    """Retrieve or update leave request details."""
    permission_classes = [IsAuthenticated]
    serializer_class = HostelLeaveSerializer

    def get_object(self):
        """Get leave by ID."""
        return get_object_or_404(HostelLeave, pk=self.kwargs['pk'])


class LeaveApproveView(generics.UpdateAPIView):
    """Approve a leave request."""
    permission_classes = [IsAuthenticated]
    serializer_class = HostelLeaveApprovalSerializer

    def get_object(self):
        """Get leave by ID."""
        return get_object_or_404(HostelLeave, pk=self.kwargs['pk'])

    def perform_update(self, serializer):
        """Approve leave via service."""
        leave = self.get_object()
        staff = selectors.get_staff(self.request.user.id)
        if not staff:
             from rest_framework.exceptions import PermissionDenied
             raise PermissionDenied("Only staff can approve leaves.")
             
        services.approve_leave(
            leave_id=leave.id,
            processed_by=staff,
            remarks=serializer.validated_data.get('remarks')
        )


class LeaveRejectView(generics.UpdateAPIView):
    """Reject a leave request."""
    permission_classes = [IsAuthenticated]
    serializer_class = HostelLeaveApprovalSerializer

    def get_object(self):
        """Get leave by ID."""
        return get_object_or_404(HostelLeave, pk=self.kwargs['pk'])

    def perform_update(self, serializer):
        """Reject leave via service."""
        leave = self.get_object()
        staff = selectors.get_staff(self.request.user.id)
        if not staff:
             from rest_framework.exceptions import PermissionDenied
             raise PermissionDenied("Only staff can reject leaves.")

        services.reject_leave(
            leave_id=leave.id,
            processed_by=staff,
            rejection_reason=serializer.validated_data.get('rejection_reason', '')
        )


# ══════════════════════════════════════════════════════════════
# COMPLAINT MANAGEMENT VIEWS (HM-WF-102)
# ══════════════════════════════════════════════════════════════

class ComplaintListCreateView(generics.ListCreateAPIView):
    """List complaints or submit a new complaint."""
    permission_classes = [IsAuthenticated]
    serializer_class = HostelComplaintSerializer

    def get_queryset(self):
        """Get complaints for authenticated user or all if staff."""
        user = self.request.user
        if user.is_staff:
            return selectors.get_all_complaints()
        return selectors.get_student_complaints(user)

    def perform_create(self, serializer):
        """Submit complaint via service."""
        try:
            student = selectors.get_student(self.request.user.id)
            if not student:
                 raise HostelManagementException("Only students can submit complaints.")

            services.create_complaint(
                student=student,
                category=serializer.validated_data['category'],
                title=serializer.validated_data['title'],
                description=serializer.validated_data['description'],
                priority=serializer.validated_data.get('priority'),
                location=serializer.validated_data.get('location')
            )
        except (ComplaintEligibilityError, ComplaintRoutingError, HostelManagementException) as e:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'detail': str(e)})


class ComplaintMyListView(generics.ListAPIView):
    """List only the authenticated user's complaints."""
    permission_classes = [IsAuthenticated]
    serializer_class = HostelComplaintSerializer

    def get_queryset(self):
        return selectors.get_student_complaints(self.request.user)


class ComplaintRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    """Retrieve or update complaint details."""
    permission_classes = [IsAuthenticated]
    serializer_class = HostelComplaintSerializer

    def get_object(self):
        """Get complaint by ID."""
        return get_object_or_404(HostelComplaint, pk=self.kwargs['pk'])

    def perform_update(self, serializer):
        """Update complaint via service."""
        complaint = self.get_object()
        services.update_complaint(
            complaint_id=complaint.id,
            status=serializer.validated_data.get('status'),
            resolution_notes=serializer.validated_data.get('resolution_remarks')
        )


class ComplaintEscalateView(generics.UpdateAPIView):
    """Escalate complaint to warden."""
    permission_classes = [IsAuthenticated]
    serializer_class = HostelComplaintUpdateSerializer

    def get_object(self):
        """Get complaint by ID."""
        return get_object_or_404(HostelComplaint, pk=self.kwargs['pk'])

    def perform_update(self, serializer):
        """Escalate complaint via service."""
        complaint = self.get_object()
        faculty = selectors.get_faculty(self.request.user.id)
        if not faculty:
             from rest_framework.exceptions import PermissionDenied
             raise PermissionDenied("Only faculty (Wardens) can handle escalation.")

        try:
            services.escalate_complaint(
                complaint_id=complaint.id,
                warden=faculty
            )
        except (EscalationAuthorizationError, WardenAuthorityError, HostelManagementException) as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ComplaintResolveView(generics.UpdateAPIView):
    """Mark complaint as resolved."""
    permission_classes = [IsAuthenticated]
    serializer_class = HostelComplaintUpdateSerializer

    def get_object(self):
        """Get complaint by ID."""
        return get_object_or_404(HostelComplaint, pk=self.kwargs['pk'])

    def perform_update(self, serializer):
        """Resolve complaint via service."""
        complaint = self.get_object()
        services.resolve_complaint(
            complaint_id=complaint.id,
            resolution_notes=serializer.validated_data.get('resolution_notes', '')
        )


# ══════════════════════════════════════════════════════════════
# HM-WF-103: ACCOMMODATION REQUEST & ALLOTMENT VIEWS
# ══════════════════════════════════════════════════════════════

class ListWindowsView(generics.ListAPIView):
    """List all accommodation application windows."""
    permission_classes = [IsAuthenticated]
    serializer_class = serializers.AccommodationApplicationWindowSerializer
    queryset = selectors.list_all_application_windows()


class SubmitAccommodationRequestView(generics.CreateAPIView):
    """Submit a new accommodation request (Student only)."""
    permission_classes = [IsStudent]
    serializer_class = serializers.AccommodationRequestSerializer

    def perform_create(self, serializer):
        try:
            student = getattr(self.request.user, 'student', None)
            if not student:
                raise HostelManagementException("User profile not found.")

            services.create_accommodation_request(
                student=student,
                window_id=self.request.data.get('window'),
                preferred_hostel_type=self.request.data.get('preferred_hostel_type'),
                preferred_room_type=self.request.data.get('preferred_room_type')
            )
        except ApplicationWindowError as e:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'detail': str(e)})


class ListRequestsView(generics.ListAPIView):
    """List all pending accommodation requests."""
    permission_classes = [IsSuperAdmin | IsWardenOrCaretaker]
    serializer_class = serializers.AccommodationRequestSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        window_id = self.request.query_params.get('window_id')
        return selectors.list_pending_requests(window_id)


class RoomCapacityDashboardView(generics.ListAPIView):
    """View hostel capacity and occupancy dashboard."""
    permission_classes = [IsSuperAdmin | IsWardenOrCaretaker]
    serializer_class = serializers.RoomCapacityDashboardSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Hostel.objects.prefetch_related('rooms_setup')
        
        if user.is_superuser:
            return queryset.all()
        
        # Filter for Warden/Caretaker assigned hostels
        assigned_query = selectors.list_assigned_hostels(user)
        return queryset.filter(hall_id__in=assigned_query.values_list('hall_id', flat=True))


class MyAllotmentView(generics.RetrieveAPIView):
    """View the active allotment for the current authenticated student."""
    permission_classes = [IsAuthenticated]
    serializer_class = serializers.RoomAllotmentSerializer

    def get_object(self):
        # Use same pattern as selectors.get_student for 100% consistency
        student = selectors.get_student(self.request.user)
        if not student:
            return None
        
        allotment = selectors.get_active_allotment_by_student(student)
        if not allotment:
            # We raise a standard DRF NotFound to avoid ambiguity with generic 404s
            from rest_framework.exceptions import NotFound
            raise NotFound("No active or legacy allotment found for current student.")
        
        return allotment


class BulkAllotmentView(generics.GenericAPIView):
    """Perform bulk allotment for selected requests."""
    permission_classes = [IsSuperAdmin | IsWardenOrCaretaker]
    serializer_class = serializers.BulkAllotmentSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        request_ids = serializer.validated_data.get('request_ids')
        results = services.perform_bulk_allotment_logic(
            request_ids=request_ids,
            allotted_by=request.user
        )
        
        return Response(results, status=status.HTTP_200_OK)


class BulkBatchAllocationView(generics.GenericAPIView):
    """
    Perform bulk batch allocation for a hostel.
    Allocates students sequentially by floor and room number.
    """
    permission_classes = [IsSuperAdmin | IsWardenOrCaretaker]
    serializer_class = serializers.BatchAllocationSerializer

    def post(self, request, pk, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            results = services.perform_bulk_batch_allocation(
                hall_id=pk,
                programme_category=serializer.validated_data.get('programme_category'),
                admission_year=serializer.validated_data.get('admission_year'),
                gender=serializer.validated_data.get('gender'),
                allotted_by=request.user
            )
            return Response(results, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f'An unexpected error occurred during allocation: {str(e)}'}, 
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class RoomAllotmentListView(generics.ListAPIView):
    """
    Administrative list of room allotments.
    - SuperAdmin: View all (can filter by hall)
    - Warden/Caretaker: View only for their assigned halls
    - Chunks: StandardPagination (50 per page)
    """
    serializer_class = serializers.RoomAllotmentSerializer
    pagination_class = StandardPagination
    
    def get_permissions(self):
        # Accessible by SuperAdmin, Warden, or Caretaker
        return [IsAuthenticated(), (IsSuperAdmin | IsWardenOrCaretaker)()]

    def get_queryset(self):
        user = self.request.user
        hall_id = self.request.query_params.get('hall') # Hall filter (actually hostel.hall_id)

        if user.is_superuser:
            # Show all for Super Admin
            return selectors.list_active_room_allotments(hall_id=hall_id)
        
        # Determine accessible hostels for Warden/Caretaker using robust selector
        assigned_hostels = selectors.list_assigned_hostels(user)
        assigned_hall_ids = list(assigned_hostels.values_list('hall_id', flat=True))

        if not assigned_hall_ids:
            return RoomAllotment.objects.none()

        # If hall filter provided, ensure it's within assigned hostels
        if hall_id and hall_id in assigned_hall_ids:
            return selectors.list_active_room_allotments(hall_id=hall_id)
        
        # Return all allotments in assigned hostels, ordered by most recent
        return RoomAllotment.objects.filter(
            hostel_id__in=assigned_hall_ids,
            is_active=True
        ).order_by('-allotted_at')
        return RoomAllotment.objects.filter(
            hostel__hall_id__in=assigned_hostels,
            is_active=True
        ).select_related('student__id__user', 'room', 'hostel').order_by('room__room_number')


# ══════════════════════════════════════════════════════════════
# ROOM CHANGE VIEWS (HM-WF-104)
# ══════════════════════════════════════════════════════════════

class RoomChangeListCreateView(generics.ListCreateAPIView):
    """List room changes or request a room change."""
    permission_classes = [IsAuthenticated]
    serializer_class = RoomAllocationChangeSerializer

    def get_queryset(self):
        """Get room changes for user or all if staff."""
        user = self.request.user
        if user.is_staff:
            return selectors.get_all_room_changes()
        return selectors.get_student_room_changes(user)

    def perform_create(self, serializer):
        """Request room change via service."""
        try:
            services.request_room_change(
                student=self.request.user,
                current_room=serializer.validated_data['current_room'],
                requested_room=serializer.validated_data['requested_room'],
                reason=serializer.validated_data['reason']
            )
        except (RoomChangeEligibilityError, HostelManagementException) as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class RoomChangeRetrieveView(generics.RetrieveAPIView):
    """Retrieve room change request details."""
    permission_classes = [IsAuthenticated]
    serializer_class = RoomAllocationChangeSerializer

    def get_object(self):
        """Get room change by ID."""
        return get_object_or_404(RoomAllocationChange, pk=self.kwargs['pk'])


class RoomChangeApproveView(generics.UpdateAPIView):
    """Approve a room change request."""
    permission_classes = [IsAuthenticated]
    serializer_class = RoomAllocationChangeApprovalSerializer

    def get_object(self):
        """Get room change by ID."""
        return get_object_or_404(RoomAllocationChange, pk=self.kwargs['pk'])

    def perform_update(self, serializer):
        """Approve room change via service."""
        room_change = self.get_object()
        try:
            services.approve_room_change(
                change_id=room_change.id,
                approved_by=self.request.user,
                remarks=serializer.validated_data.get('remarks')
            )
        except (RoomChangeEligibilityError, DualApprovalError, AllotmentCapacityError, HostelManagementException) as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class RoomChangeRejectView(generics.UpdateAPIView):
    """Reject a room change request."""
    permission_classes = [IsAuthenticated]
    serializer_class = RoomAllocationChangeApprovalSerializer

    def get_object(self):
        """Get room change by ID."""
        return get_object_or_404(RoomAllocationChange, pk=self.kwargs['pk'])

    def perform_update(self, serializer):
        """Reject room change via service."""
        room_change = self.get_object()
        services.reject_room_change(
            change_id=room_change.id,
            rejection_reason=serializer.validated_data.get('rejection_reason', '')
        )


# ══════════════════════════════════════════════════════════════
# FINE MANAGEMENT VIEWS (HM-WF-105)
# ══════════════════════════════════════════════════════════════

class FineListCreateView(generics.ListCreateAPIView):
    """List fines or impose a new fine."""
    permission_classes = [IsAuthenticated]
    serializer_class = HostelFineSerializer

    def get_queryset(self):
        """Get fines for user or all if staff."""
        user = self.request.user
        if user.is_staff:
            return selectors.get_all_fines()
        return selectors.get_student_fines(user)

    def perform_create(self, serializer):
        """Impose fine via service."""
        try:
            services.impose_fine(
                student_id=serializer.validated_data['student'].id,
                fine_type=serializer.validated_data['fine_type'],
                amount=serializer.validated_data['amount'],
                reason=serializer.validated_data['reason'],
                due_date=serializer.validated_data['due_date'],
                issued_by=self.request.user
            )
        except (FineValidationError, HostelManagementException) as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class FineRetrieveView(generics.RetrieveAPIView):
    """Retrieve fine details."""
    permission_classes = [IsAuthenticated]
    serializer_class = HostelFineSerializer

    def get_object(self):
        """Get fine by ID."""
        return get_object_or_404(HostelFine, pk=self.kwargs['pk'])


class FineMarkPaidView(generics.UpdateAPIView):
    """Mark fine as paid."""
    permission_classes = [IsAuthenticated]
    serializer_class = HostelFinePaymentSerializer

    def get_object(self):
        """Get fine by ID."""
        return get_object_or_404(HostelFine, pk=self.kwargs['pk'])

    def perform_update(self, serializer):
        """Mark fine as paid via service."""
        fine = self.get_object()
        services.mark_fine_paid(
            fine_id=fine.id,
            paid_date=serializer.validated_data.get('paid_date')
        )


class FineWaiveView(generics.UpdateAPIView):
    """Waive a fine."""
    permission_classes = [IsAuthenticated]
    serializer_class = HostelFineWaiverSerializer

    def get_object(self):
        """Get fine by ID."""
        return get_object_or_404(HostelFine, pk=self.kwargs['pk'])

    def perform_update(self, serializer):
        """Waive fine via service."""
        fine = self.get_object()
        services.waive_fine(
            fine_id=fine.id,
            waived_by=self.request.user,
            reason=serializer.validated_data.get('waive_reason', '')
        )


# ══════════════════════════════════════════════════════════════
# STAFF SCHEDULE VIEWS (HM-WF-107)
# ══════════════════════════════════════════════════════════════

class StaffScheduleListCreateView(generics.ListCreateAPIView):
    """List schedules or create a new schedule."""
    permission_classes = [IsAuthenticated]
    serializer_class = StaffScheduleSerializer

    def get_queryset(self):
        """Get all staff schedules."""
        return selectors.get_all_schedules()

    def perform_create(self, serializer):
        """Create schedule via service."""
        services.create_staff_schedule(
            hall_id=serializer.validated_data['hall'].id,
            staff_id=serializer.validated_data['staff'].id,
            day_of_week=serializer.validated_data['day_of_week'],
            start_time=serializer.validated_data['start_time'],
            end_time=serializer.validated_data['end_time'],
            shift_type=serializer.validated_data.get('shift_type')
        )


class StaffScheduleRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a schedule."""
    permission_classes = [IsAuthenticated]
    serializer_class = StaffScheduleSerializer

    def get_object(self):
        """Get schedule by ID."""
        return get_object_or_404(StaffSchedule, pk=self.kwargs['pk'])


# ══════════════════════════════════════════════════════════════
# INVENTORY MANAGEMENT VIEWS (HM-WF-108)
# ══════════════════════════════════════════════════════════════

class InventoryListCreateView(generics.ListCreateAPIView):
    """List inventory items or add a new item."""
    permission_classes = [IsAuthenticated]
    serializer_class = HostelInventorySerializer

    def get_queryset(self):
        """Get all inventory items."""
        return selectors.get_all_inventory()

    def perform_create(self, serializer):
        """Add inventory item via service."""
        services.add_inventory_item(
            hall_id=serializer.validated_data['hall'].id,
            item_name=serializer.validated_data['item_name'],
            quantity=serializer.validated_data['quantity'],
            unit_cost=serializer.validated_data['unit_cost'],
            remarks=serializer.validated_data.get('remarks')
        )


class InventoryRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    """Retrieve or update inventory item."""
    permission_classes = [IsAuthenticated]
    serializer_class = HostelInventorySerializer

    def get_object(self):
        """Get inventory by ID."""
        return get_object_or_404(HostelInventory, pk=self.kwargs['pk'])

    def perform_update(self, serializer):
        """Update inventory via service."""
        inventory = self.get_object()
        services.update_inventory(
            inventory_id=inventory.id,
            quantity=serializer.validated_data.get('quantity'),
            remarks=serializer.validated_data.get('remarks')
        )


# ...existing code...


# ══════════════════════════════════════════════════════════════
# GUEST ROOM BOOKING VIEWS (HM-WF-112)
# ══════════════════════════════════════════════════════════════

class GuestBookingListCreateView(generics.ListCreateAPIView):
    """List guest bookings or request guest room."""
    permission_classes = [IsAuthenticated]
    serializer_class = GuestRoomBookingSerializer

    def get_serializer_class(self):
        
        """Use appropriate serializer based on request method."""
        if self.request.method == 'POST':
            return GuestRoomBookingCreateSerializer
        return GuestRoomBookingSerializer

    
    def get_queryset(self):
        """Get bookings for user or all if staff."""
        user = self.request.user
        if user.is_staff:
            return selectors.get_all_guest_bookings()
        return selectors.get_student_guest_bookings(user)
    def perform_create(self, serializer):
        """Request guest room via service."""
        services.request_guest_room(
            student=self.request.user,
            guest_name=serializer.validated_data['guest_name'],
            guest_phone=serializer.validated_data['guest_phone'],
            arrival_date=serializer.validated_data['arrival_date'],
            departure_date=serializer.validated_data['departure_date'],
            purpose=serializer.validated_data['purpose'],
            total_guests=serializer.validated_data['total_guests'],
            guest_email=serializer.validated_data.get('guest_email', ''),
            guest_address=serializer.validated_data.get('guest_address', ''),
            nationality=serializer.validated_data.get('nationality', ''),
            rooms_required=serializer.validated_data.get('rooms_required', 1),
            room_type=serializer.validated_data.get('room_type', 'single')
        )


class GuestBookingRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    """Retrieve or update guest booking."""
    permission_classes = [IsAuthenticated]
    serializer_class = GuestRoomBookingSerializer

    def get_object(self):
        """Get booking by ID."""
        return get_object_or_404(GuestRoomBooking, pk=self.kwargs['pk'])


class GuestBookingApproveView(generics.UpdateAPIView):
    """Approve guest room booking."""
    permission_classes = [IsAuthenticated]
    serializer_class = GuestRoomBookingApprovalSerializer

    def get_object(self):
        """Get booking by ID."""
        return get_object_or_404(GuestRoomBooking, pk=self.kwargs['pk'])

    def perform_update(self, serializer):
        """Approve booking via service."""
        booking = self.get_object()
        services.approve_guest_booking(
            booking_id=booking.id,
            approved_by=self.request.user,
            remarks=serializer.validated_data.get('review_remarks', '')
        )


class GuestBookingRejectView(generics.UpdateAPIView):
    """Reject guest room booking."""
    permission_classes = [IsAuthenticated]
    serializer_class = GuestRoomBookingApprovalSerializer

    def get_object(self):
        """Get booking by ID."""
        return get_object_or_404(GuestRoomBooking, pk=self.kwargs['pk'])

    def perform_update(self, serializer):
        """Reject booking via service."""
        booking = self.get_object()
        services.reject_guest_booking(
            booking_id=booking.id,
            rejection_reason=serializer.validated_data.get('review_remarks', '')
        )


class GuestBookingCheckInView(generics.UpdateAPIView):
    """Check in guest."""
    permission_classes = [IsAuthenticated]
    serializer_class = GuestRoomBookingApprovalSerializer

    def get_object(self):
        """Get booking by ID."""
        return get_object_or_404(GuestRoomBooking, pk=self.kwargs['pk'])

    def perform_update(self, serializer):
        """Check in guest via service."""
        booking = self.get_object()
        services.check_in_guest(booking_id=booking.id)


class GuestBookingCheckOutView(generics.UpdateAPIView):
    """Check out guest."""
    permission_classes = [IsAuthenticated]
    serializer_class = GuestRoomBookingApprovalSerializer

    def get_object(self):
        """Get booking by ID."""
        return get_object_or_404(GuestRoomBooking, pk=self.kwargs['pk'])

    def perform_update(self, serializer):
        """Check out guest via service."""
        booking = self.get_object()
        services.check_out_guest(booking_id=booking.id)


# ══════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════
# NOTICE BOARD VIEWS (HM-WF-110)
# ══════════════════════════════════════════════════════════════

class NoticeListView(generics.ListCreateAPIView):
    """List all active notices for current hall or create a new notice."""
    permission_classes = [IsAuthenticated]
    serializer_class = HostelNoticeBoardSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        """Get active notices for the hall."""
        hall_id = self.request.query_params.get('hall_id')
        if hall_id:
            return selectors.list_active_notices(hall_id)
        # Return empty if no hall specified
        return HostelNoticeBoard.objects.none()

    def perform_create(self, serializer):
        """Create notice with current user as poster and auto-assign hall."""
        from rest_framework import serializers as drf_serializers
        
        # Get hall_id from request data or query params
        hall_id = self.request.data.get('hall_id') or self.request.query_params.get('hall_id')
        
        if not hall_id:
            raise drf_serializers.ValidationError({'hall_id': 'hall_id is required to post a notice'})
        
        hall = get_object_or_404(Hostel, pk=hall_id)
        serializer.save(posted_by=self.request.user, hall=hall)


class NoticeRetrieveView(generics.RetrieveAPIView):
    """Retrieve a specific notice."""
    permission_classes = [IsAuthenticated]
    serializer_class = HostelNoticeBoardSerializer

    def get_object(self):
        """Get notice by ID."""
        return get_object_or_404(HostelNoticeBoard, pk=self.kwargs['pk'])


# ══════════════════════════════════════════════════════════════
# NEW FEATURE VIEWS (Room Vacation & Extended Stay)
# ══════════════════════════════════════════════════════════════

from .serializers import RoomVacationRequestSerializer, ExtendedStayApplicationSerializer
from ..selectors import list_room_vacations, get_room_vacation, list_extended_stays, get_extended_stay

class RoomVacationListCreateView(generics.ListCreateAPIView):
    serializer_class = RoomVacationRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        filters = {}
        if not self.request.user.is_staff and not self.request.user.is_superuser:
            filters['student'] = getattr(self.request.user, 'student', None)
        return list_room_vacations(filters)

    def perform_create(self, serializer):
        serializer.save(student=self.request.user.student)

class RoomVacationDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = RoomVacationRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        filters = {}
        if not self.request.user.is_staff and not self.request.user.is_superuser:
            filters['student'] = getattr(self.request.user, 'student', None)
        return list_room_vacations(filters)

class RoomVacationVerifyView(generics.UpdateAPIView):
    serializer_class = RoomVacationRequestSerializer
    permission_classes = [IsAdminUser]

    def update(self, request, *args, **kwargs):
        from ..services import process_room_vacation
        try:
            remarks = request.data.get('remarks', '')
            obj = process_room_vacation(kwargs['pk'], 'verify', remarks)
            return Response({'status': obj.status})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

class RoomVacationApproveView(generics.UpdateAPIView):
    serializer_class = RoomVacationRequestSerializer
    permission_classes = [IsAdminUser]

    def update(self, request, *args, **kwargs):
        from ..services import process_room_vacation
        try:
            remarks = request.data.get('remarks', '')
            obj = process_room_vacation(kwargs['pk'], 'approve', remarks)
            return Response({'status': obj.status})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


class ExtendedStayListCreateView(generics.ListCreateAPIView):
    serializer_class = ExtendedStayApplicationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        filters = {}
        if not self.request.user.is_staff and not self.request.user.is_superuser:
            filters['student'] = getattr(self.request.user, 'student', None)
        return list_extended_stays(filters)

    def create(self, request, *args, **kwargs):
        from ..services import create_extended_stay
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            student = getattr(self.request.user, 'student', None)
            if not student:
                return Response({"error": "User is not a student."}, status=400)
                
            stay = create_extended_stay(
                student=student,
                start_date=serializer.validated_data['start_date'],
                end_date=serializer.validated_data['end_date'],
                reason=serializer.validated_data['reason']
            )
            return Response(ExtendedStayApplicationSerializer(stay).data, status=201)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

class ExtendedStayDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ExtendedStayApplicationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        filters = {}
        if not self.request.user.is_staff and not self.request.user.is_superuser:
            filters['student'] = getattr(self.request.user, 'student', None)
        return list_extended_stays(filters)

class ExtendedStayApproveView(generics.UpdateAPIView):
    serializer_class = ExtendedStayApplicationSerializer
    permission_classes = [IsAdminUser]
    
    def update(self, request, *args, **kwargs):
        try:
            obj = get_extended_stay(kwargs['pk'])
            obj.status = 'approved'
            obj.remarks = request.data.get('remarks', obj.remarks)
            obj.save()
            return Response({'status': 'approved'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

class ExtendedStayRejectView(generics.UpdateAPIView):
    serializer_class = ExtendedStayApplicationSerializer
    permission_classes = [IsAdminUser]
    
    def update(self, request, *args, **kwargs):
        try:
            obj = get_extended_stay(kwargs['pk'])
            obj.status = 'rejected'
            obj.remarks = request.data.get('remarks', obj.remarks)
            obj.save()
            return Response({'status': 'rejected'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


# ══════════════════════════════════════════════════════════════
# ATTENDANCE MANAGEMENT VIEWS
# ══════════════════════════════════════════════════════════════

class AttendanceByHostelView(generics.ListAPIView):
    """List attendance for a hostel on a specific date."""
    permission_classes = [IsWardenOrCaretaker]
    serializer_class = HostelAttendanceSerializer

    def get_queryset(self):
        hall_id = self.request.query_params.get('hall_id')
        date_str = self.request.query_params.get('date')
        if not hall_id:
             return HostelStudentAttendance.objects.none()
        
        if date_str:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                date = timezone.now().date()
        else:
            date = timezone.now().date()
        
        return selectors.get_attendance_by_hostel(hall_id, date)


class AttendanceMarkView(generics.CreateAPIView):
    """Bulk mark attendance for a hall."""
    permission_classes = [IsAuthenticated]
    serializer_class = HostelAttendanceSerializer

    def post(self, request, *args, **kwargs):
        hall_id = request.data.get('hall_id')
        date_str = request.data.get('date')
        attendance_data = request.data.get('attendance', [])
        
        if not hall_id or not date_str:
            return Response({'error': 'hall_id and date are required'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            hostel = Hostel.objects.filter(hall_id=hall_id).first()
            if not hostel:
                return Response({'error': f'Hostel {hall_id} not found'}, status=status.HTTP_404_NOT_FOUND)
            
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            records = services.mark_attendance(hostel, date, attendance_data)
            serializer = self.get_serializer(records, many=True)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ══════════════════════════════════════════════════════════════
# HOSTEL SETUP FOUNDATION VIEWS
# ══════════════════════════════════════════════════════════════

from ..models import (
    HostelAuditLog, StaffRoleChoices, HostelStatusChoices as HostelOpStatusChoices
)
from ..permissions import IsHostelSuperAdmin, IsAssignedToHostel
from .serializers import (
    HostelSetupSerializer, HostelCreateSerializer, HostelStatusSerializer,
    StaffAssignmentSerializer, StaffAssignmentCreateSerializer,
    HostelAuditLogSerializer
)


class CreateHostelView(generics.CreateAPIView):
    """Create a new hostel (SuperAdmin only). Rooms auto-created via post_save signal."""
    permission_classes = [IsHostelSuperAdmin]
    serializer_class = HostelCreateSerializer

    def perform_create(self, serializer):
        hostel = serializer.save(created_by=self.request.user)
        # Write audit log
        HostelAuditLog.objects.create(
            hostel=hostel,
            action='HOSTEL_CREATED',
            performed_by=self.request.user,
            detail_json={
                'name': hostel.name,
                'type': hostel.type,
                'total_capacity': hostel.total_capacity,
                'floor_count': hostel.floor_count,
                'rooms_created': hostel.rooms_setup.count(),
            }
        )

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        # Return with full serializer
        hall_id = response.data.get('hall_id')
        hostel = Hostel.objects.get(hall_id=hall_id)
        return Response(
            HostelSetupSerializer(hostel).data,
            status=status.HTTP_201_CREATED
        )


class ListHostelsView(generics.ListAPIView):
    """
    List hostels with warden info.
    - SuperAdmins see all hostels.
    - Wardens and Caretakers see only their assigned hostels (modern or legacy).
    """
    permission_classes = [IsHostelSuperAdmin | IsWardenOrCaretaker]
    serializer_class = HostelSetupSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Hostel.objects.prefetch_related(
            'staff_assignments', 'staff_assignments__user', 'rooms_setup'
        )
        
        if user.is_superuser:
            return queryset.all()
        
        # Filter by assigned hostels (including legacy mapping)
        assigned_query = selectors.list_assigned_hostels(user)
        return queryset.filter(hall_id__in=assigned_query.values_list('hall_id', flat=True))


class RetrieveHostelView(generics.RetrieveAPIView):
    """Retrieve a single hostel's details."""
    permission_classes = [IsAssignedToHostel]
    serializer_class = HostelSetupSerializer

    def get_queryset(self):
        return Hostel.objects.prefetch_related(
            'staff_assignments', 'staff_assignments__user', 'rooms_setup'
        ).all()


class ManageHostelStatusView(generics.GenericAPIView):
    """
    Change hostel status (SuperAdmin only).

    Enforces:
    - BR-HM-008.a: Block deactivation if occupied rooms
    - BR-HM-008.b / BR-HM-019.a: Block activation without warden+caretaker
    - All changes written to HostelAuditLog
    """
    permission_classes = [IsHostelSuperAdmin]
    serializer_class = HostelStatusSerializer

    def patch(self, request, pk, *args, **kwargs):
        hostel = get_object_or_404(Hostel, pk=pk)
        serializer = self.get_serializer(
            data=request.data, context={'hostel': hostel}
        )
        serializer.is_valid(raise_exception=True)

        old_status = hostel.status
        new_status = serializer.validated_data['status']

        hostel.status = new_status
        hostel.save(update_fields=['status', 'updated_at'])

        # Write audit log
        HostelAuditLog.objects.create(
            hostel=hostel,
            action='STATUS_CHANGED',
            performed_by=request.user,
            detail_json={
                'from_status': old_status,
                'to_status': new_status,
            }
        )

        return Response(
            HostelSetupSerializer(hostel).data,
            status=status.HTTP_200_OK
        )


class AssignWardenView(generics.GenericAPIView):
    """
    Assign a warden to a hostel (SuperAdmin only).

    Deactivates any previous active warden for this hostel before creating
    the new assignment. Writes to HostelAuditLog.
    """
    permission_classes = [IsHostelSuperAdmin]
    serializer_class = StaffAssignmentCreateSerializer

    def post(self, request, pk, *args, **kwargs):
        hostel = get_object_or_404(Hostel, pk=pk)
        data = request.data.copy()
        data['role'] = StaffRoleChoices.WARDEN
        serializer = self.get_serializer(data=data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.get(id=serializer.validated_data['user_id'])
        warning = serializer.validated_data.get('_warning')

        # Block if a warden is already assigned
        active_warden = HostelStaffAssignment.objects.filter(
            hostel=hostel, role=StaffRoleChoices.WARDEN, is_active=True
        ).exists()

        if active_warden:
            return Response(
                {"error": "This hostel already has an active Warden assigned. Please remove the existing assignment first."},
                status=status.HTTP_400_BAD_REQUEST
            )

        assignment = HostelStaffAssignment.objects.create(
            hostel=hostel,
            user=user,
            role=StaffRoleChoices.WARDEN,
            start_date=serializer.validated_data['start_date'],
            end_date=serializer.validated_data.get('end_date'),
            is_active=True,
            assigned_by=request.user
        )

        # Write audit log
        HostelAuditLog.objects.create(
            hostel=hostel,
            action='WARDEN_ASSIGNED',
            performed_by=request.user,
            detail_json={
                'user_id': user.id,
                'user_name': user.get_full_name() or user.username,
                'start_date': str(assignment.start_date),
            }
        )

        result = StaffAssignmentSerializer(assignment).data
        if warning:
            result['warning'] = warning

        return Response(result, status=status.HTTP_201_CREATED)


class AssignCaretakerView(generics.GenericAPIView):
    """
    Assign a caretaker to a hostel (SuperAdmin only).

    Deactivates any previous active caretaker for this hostel before creating
    the new assignment. Writes to HostelAuditLog.
    """
    permission_classes = [IsHostelSuperAdmin]
    serializer_class = StaffAssignmentCreateSerializer

    def post(self, request, pk, *args, **kwargs):
        hostel = get_object_or_404(Hostel, pk=pk)
        data = request.data.copy()
        data['role'] = StaffRoleChoices.CARETAKER
        serializer = self.get_serializer(data=data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.get(id=serializer.validated_data['user_id'])
        warning = serializer.validated_data.get('_warning')

        # Block if a caretaker is already assigned
        active_caretaker = HostelStaffAssignment.objects.filter(
            hostel=hostel, role=StaffRoleChoices.CARETAKER, is_active=True
        ).exists()

        if active_caretaker:
            return Response(
                {"error": "This hostel already has an active Caretaker assigned. Please remove the existing assignment first."},
                status=status.HTTP_400_BAD_REQUEST
            )

        assignment = HostelStaffAssignment.objects.create(
            hostel=hostel,
            user=user,
            role=StaffRoleChoices.CARETAKER,
            start_date=serializer.validated_data['start_date'],
            end_date=serializer.validated_data.get('end_date'),
            is_active=True,
            assigned_by=request.user
        )

        HostelAuditLog.objects.create(
            hostel=hostel,
            action='CARETAKER_ASSIGNED',
            performed_by=request.user,
            detail_json={
                'user_id': user.id,
                'user_name': user.get_full_name() or user.username,
                'start_date': str(assignment.start_date),
            }
        )

        result = StaffAssignmentSerializer(assignment).data
        if warning:
            result['warning'] = warning

        return Response(result, status=status.HTTP_201_CREATED)


class ReassignStaffView(generics.GenericAPIView):
    """
    Reassign staff on a hostel (SuperAdmin only).

    If removing the only Warden or Caretaker, a replacement must be provided
    in the same request. Both old_assignment_id and new user data required.
    """
    permission_classes = [IsHostelSuperAdmin]

    def post(self, request, pk, *args, **kwargs):
        hostel = get_object_or_404(Hostel, pk=pk)

        old_assignment_id = request.data.get('old_assignment_id')
        new_user_id = request.data.get('new_user_id')
        start_date = request.data.get('start_date')

        if not old_assignment_id or not new_user_id or not start_date:
            return Response(
                {'error': 'old_assignment_id, new_user_id, and start_date are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        old_assignment = get_object_or_404(
            HostelStaffAssignment, pk=old_assignment_id, hostel=hostel
        )
        new_user = get_object_or_404(User, pk=new_user_id)

        role = old_assignment.role

        # Check: if removing the only active assignment of this role, block
        active_same_role = HostelStaffAssignment.objects.filter(
            hostel=hostel, role=role, is_active=True
        ).exclude(pk=old_assignment.pk).count()

        if active_same_role == 0 and hostel.status == HostelOpStatusChoices.ACTIVE:
            # Must be a replacement — which is what this endpoint does
            pass

        # Deactivate old
        old_assignment.is_active = False
        old_assignment.end_date = timezone.now().date()
        old_assignment.save()

        # Create new
        new_assignment = HostelStaffAssignment.objects.create(
            hostel=hostel,
            user=new_user,
            role=role,
            start_date=start_date,
            is_active=True,
            assigned_by=request.user
        )

        HostelAuditLog.objects.create(
            hostel=hostel,
            action='STAFF_REASSIGNED',
            performed_by=request.user,
            detail_json={
                'role': role,
                'old_user_id': old_assignment.user.id,
                'old_user_name': old_assignment.user.get_full_name() or old_assignment.user.username,
                'new_user_id': new_user.id,
                'new_user_name': new_user.get_full_name() or new_user.username,
            }
        )

        return Response(
            StaffAssignmentSerializer(new_assignment).data,
            status=status.HTTP_200_OK
        )


class ListStaffAssignmentsView(generics.ListAPIView):
    """
    List staff assignments for a hostel.
    - Accessible only by SuperAdmins or assigned Wardens/Caretakers.
    """
    permission_classes = [IsHostelSuperAdmin | IsAssignedToHostel]
    serializer_class = serializers.StaffAssignmentSerializer

    def get_queryset(self):
        hostel_id = self.kwargs.get('pk')
        return HostelStaffAssignment.objects.filter(
            hostel_id=hostel_id
        ).select_related('user', 'hostel', 'assigned_by')


class RemoveStaffAssignmentView(generics.GenericAPIView):
    """
    Remove (deactivate) an active staff assignment (SuperAdmin only).
    """
    permission_classes = [IsHostelSuperAdmin]

    def post(self, request, pk, *args, **kwargs):
        assignment = get_object_or_404(HostelStaffAssignment, pk=pk, is_active=True)
        hostel = assignment.hostel
        
        assignment.is_active = False
        assignment.end_date = timezone.now().date()
        assignment.save()

        # Write audit log
        HostelAuditLog.objects.create(
            hostel=hostel,
            action=f'{assignment.role.upper()}_REMOVED',
            performed_by=request.user,
            detail_json={
                'user_id': assignment.user.id,
                'username': assignment.user.username,
                'assignment_id': assignment.id
            }
        )

        return Response(
            serializers.HostelSetupSerializer(hostel).data,
            status=status.HTTP_200_OK
        )


class DeleteHostelView(generics.DestroyAPIView):
    """
    Permanently delete a hostel (SuperAdmin only).
    CASCADE deletes rooms, assignments, etc.
    """
    permission_classes = [IsHostelSuperAdmin]
    queryset = Hostel.objects.all()

    def perform_destroy(self, instance):
        # We can't write an audit log for an object we just deleted if it references it by FK
        # So we log it first without the FK if necessary, or just rely on global logs
        # Actually, since our AuditLog is CASCADE, if we delete the hostel, 
        # the audit log entries for that hostel will ALSO be deleted if they have a FK to it.
        # This is a drawback of CASCADE audit logs.
        super().perform_destroy(instance)
