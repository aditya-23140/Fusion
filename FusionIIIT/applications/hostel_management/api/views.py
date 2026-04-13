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

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, BasePermission
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from applications.globals.models import Staff
from applications.globals.models import Faculty


from ..models import (
    Hall, HallRoom, HostelLeave, HostelComplaint, RoomAllocation, RoomAllocationChange,
    HostelFine, StaffSchedule, HostelInventory, GuestRoomBooking,
    HostelNoticeBoard,
    HallWarden, HallCaretaker
)
from .serializers import (
    HallSerializer, HallListSerializer, HallCreateUpdateSerializer, HallRoomSerializer, HallRoomCreateUpdateSerializer,
    HostelLeaveSerializer, HostelLeaveApprovalSerializer,
    HostelComplaintSerializer, HostelComplaintUpdateSerializer,
    RoomAllocationSerializer, RoomAllocationChangeSerializer,
    RoomAllocationChangeApprovalSerializer,
    HostelFineSerializer, HostelFinePaymentSerializer, HostelFineWaiverSerializer,
    StaffScheduleSerializer, HostelInventorySerializer,
    GuestRoomBookingSerializer, GuestRoomBookingCreateSerializer, GuestRoomBookingApprovalSerializer,
    HostelNoticeBoardSerializer,
)
from .. import selectors, services
from ..exceptions import (
    LeaveEligibilityError, LeaveDateValidationError, ComplaintError,
    RoomAllocationError, RoomChangeError, FineError
)


# ══════════════════════════════════════════════════════════════
# PAGINATION & ROLE-BASED PERMISSION CLASSES
# ══════════════════════════════════════════════════════════════

class StandardPagination(PageNumberPagination):
    """Standard pagination: 50 items per page for optimized payload."""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 500
    page_query_param = 'page'


class IsSuperAdmin(BasePermission):
    """Permission for Super Admin role: hostel creation, warden/caretaker assignment, batch allocation."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_superuser


class IsWardenOrCaretaker(BasePermission):
    """Permission for Warden and Caretaker roles."""
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return HallWarden.objects.filter(faculty__id__user=request.user).exists() or \
               HallCaretaker.objects.filter(staff__id__user=request.user).exists()


class IsWarden(BasePermission):
    """Permission for Warden role only."""
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return HallWarden.objects.filter(faculty__id__user=request.user).exists()


class IsCaretaker(BasePermission):
    """Permission for Caretaker role only."""
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return HallCaretaker.objects.filter(staff__id__user=request.user).exists()


class IsStudent(BasePermission):
    """Permission for Student role."""
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        from applications.academic_information.models import Student
        return Student.objects.filter(user=request.user).exists()


# ══════════════════════════════════════════════════════════════
# HALL MANAGEMENT VIEWS
# ══════════════════════════════════════════════════════════════

class HallListCreateView(generics.ListCreateAPIView):
    """List all halls or create a new hall (Super Admin only for creation)."""
    
    def get_permissions(self):
        """Allow GET for authenticated users, POST only for super admin."""
        if self.request.method == 'POST':
            return [IsSuperAdmin()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        """Use lightweight serializer for list, full serializer for create."""
        if self.request.method == 'POST':
            return HallCreateUpdateSerializer
        # Use HallListSerializer for GET (excludes expensive number_students)
        return HallListSerializer

    def get_queryset(self):
        """Get all halls from selector."""
        return selectors.get_all_halls()

    def perform_create(self, serializer):
        """Create hall via service and auto-generate rooms."""
        # Create the hall
        hall = Hall.objects.create(
            hall_id=serializer.validated_data['hall_id'],
            hall_name=serializer.validated_data['hall_name'],
            max_accomodation=serializer.validated_data['max_accomodation'],
            assigned_batch=serializer.validated_data.get('assigned_batch'),
            type_of_seater=serializer.validated_data.get('type_of_seater')
        )
        
        # Map type_of_seater to room capacity
        capacity_map = {'single': 1, 'double': 2, 'triple': 3}
        room_capacity = capacity_map.get(hall.type_of_seater, 3)
        
        # Calculate number of rooms based on max_accomodation and room capacity
        max_occupancy = serializer.validated_data.get('max_accomodation', 100)
        num_rooms = max_occupancy // room_capacity
        
        # Auto-generate rooms in sequence (1, 2, 3, ...)
        for room_num in range(1, num_rooms + 1):
            HallRoom.objects.create(
                hall=hall,
                room_number=str(room_num),
                block_number="A",
                capacity=room_capacity,
                room_type=hall.type_of_seater,
                status='available'
            )


class HallRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a hall."""
    permission_classes = [IsAuthenticated]
    serializer_class = HallSerializer

    def get_object(self):
        """Get hall by ID."""
        return get_object_or_404(Hall, pk=self.kwargs['pk'])

# ══════════════════════════════════════════════════════════════
# HALL ROOM MANAGEMENT VIEWS
# ══════════════════════════════════════════════════════════════

class HallRoomListCreateView(generics.ListCreateAPIView):
    """List all rooms in a hall or create a new room."""
    permission_classes = [IsAuthenticated]
    serializer_class = HallRoomSerializer

    def get_serializer_class(self):
        """Use HallRoomCreateUpdateSerializer for POST, HallRoomSerializer for GET."""
        if self.request.method == 'POST':
            return HallRoomCreateUpdateSerializer
        return HallRoomSerializer

    def get_queryset(self):
        """Get all rooms for a specific hall."""
        hall_id = self.kwargs['pk']
        return HallRoom.objects.filter(hall_id=hall_id)

    def perform_create(self, serializer):
        """Create room via serializer."""
        hall_id = self.kwargs['pk']
        hall = get_object_or_404(Hall, pk=hall_id)
        serializer.save(hall=hall)


class HallRoomRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific room in a hall."""
    permission_classes = [IsAuthenticated]
    serializer_class = HallRoomSerializer

    def get_object(self):
        """Get room by ID, verifying it belongs to the specified hall."""
        hall_id = self.kwargs['hall_pk']
        room_id = self.kwargs['pk']
        return get_object_or_404(HallRoom, pk=room_id, hall_id=hall_id)


# ══════════════════════════════════════════════════════════════
# SUPER ADMIN MANAGEMENT VIEWS
# ══════════════════════════════════════════════════════════════

class WardenAssignmentView(generics.GenericAPIView):
    """Assign a warden to a hall (Super Admin only)."""
    permission_classes = [IsSuperAdmin]
    serializer_class = HallSerializer

    def post(self, request, *args, **kwargs):
        """
        Assign warden to hall by email.
        Request body: { "email": "user@example.com", "hall_id": <id> }
        """
        try:
            email = request.data.get('email')
            hall_id = request.data.get('hall_id')
            
            if not email or not hall_id:
                return Response(
                    {'error': 'email and hall_id are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get user by email
            user = get_object_or_404(User, email=email)
            
            # Get or create Faculty for this user
            faculty = Faculty.objects.filter(id__user=user).first()
            if not faculty:
                return Response(
                    {'error': f'No faculty profile found for user {email}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            hall = get_object_or_404(Hall, pk=hall_id)
            
            warden = services.assign_warden_to_hall(hall, faculty)
            
            return Response(
                {'message': f'Warden assigned to {hall.hall_name}', 'warden_id': warden.id},
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class CaretakerAssignmentView(generics.GenericAPIView):
    """Assign a caretaker to a hall (Super Admin only)."""
    permission_classes = [IsSuperAdmin]
    serializer_class = HallSerializer

    def post(self, request, *args, **kwargs):
        """
        Assign caretaker to hall by email.
        Request body: { "email": "user@example.com", "hall_id": <id> }
        """
        try:
            email = request.data.get('email')
            hall_id = request.data.get('hall_id')
            
            if not email or not hall_id:
                return Response(
                    {'error': 'email and hall_id are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            
            # Get user by email
            user = get_object_or_404(User, email=email)
            
            # Get or create Staff for this user
            staff = Staff.objects.filter(id__user=user).first()
            if not staff:
                return Response(
                    {'error': f'No staff profile found for user {email}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            hall = get_object_or_404(Hall, pk=hall_id)
            
            caretaker = services.assign_caretaker_to_hall(hall, staff)
            
            return Response(
                {'message': f'Caretaker assigned to {hall.hall_name}', 'caretaker_id': caretaker.id},
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class BatchAllocationView(generics.GenericAPIView):
    """Allocate an academic batch to a hall (Super Admin only)."""
    permission_classes = [IsSuperAdmin]
    serializer_class = HallSerializer

    def post(self, request, *args, **kwargs):
        """
        Allocate batch to hall.
        Request body: { "hall_id": <id>, "batch_id": <id> }
        """
        try:
            hall_id = request.data.get('hall_id')
            batch_id = request.data.get('batch_id')
            
            if not hall_id or not batch_id:
                return Response(
                    {'error': 'hall_id and batch_id are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            hall = get_object_or_404(Hall, pk=hall_id)
            from applications.programme_curriculum.models import AcademicBatch
            batch = get_object_or_404(AcademicBatch, id=batch_id)
            
            updated_hall = services.allocate_batch_to_hall(hall, batch)
            
            return Response(
                {'message': f'Batch allocated to {hall.hall_name}', 'batch_id': batch.id},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class ActiveBatchYearsView(generics.ListAPIView):
    """Get all active batch years for assignment (Super Admin only)."""
    permission_classes = [IsSuperAdmin]

    def get(self, request, *args, **kwargs):
        """Get active batch years."""
        try:
            batches = services.get_active_batch_years()
            return Response(
                {'batches': batches},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class StaffAssignmentListView(generics.ListAPIView):
    """List all warden and caretaker assignments."""
    permission_classes = [IsSuperAdmin]
    pagination_class = StandardPagination

    def get(self, request, *args, **kwargs):
        """Get all assignments (wardens and caretakers)."""
        try:
            wardens = HallWarden.objects.all().select_related('hall', 'faculty__id__user')
            caretakers = HallCaretaker.objects.all().select_related('hall', 'staff__id__user')
            
            assignments = []
            
            # Add wardens
            for warden in wardens:
                user = warden.faculty.id.user if warden.faculty and warden.faculty.id else None
                assignments.append({
                    'id': f'warden_{warden.id}',
                    'staff_name': user.get_full_name() if user else 'Unknown',
                    'email': user.email if user else 'N/A',
                    'hall_name': warden.hall.hall_name,
                    'role': 'warden',
                    'assigned_date': warden.assigned_date,
                })
            
            # Add caretakers
            for caretaker in caretakers:
                user = caretaker.staff.id.user if caretaker.staff and caretaker.staff.id else None
                assignments.append({
                    'id': f'caretaker_{caretaker.id}',
                    'staff_name': user.get_full_name() if user else 'Unknown',
                    'email': user.email if user else 'N/A',
                    'hall_name': caretaker.hall.hall_name,
                    'role': 'caretaker',
                    'assigned_date': caretaker.assigned_date,
                })
            
            return Response(assignments, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class StaffAssignmentDeleteView(generics.DestroyAPIView):
    """Delete a warden or caretaker assignment."""
    permission_classes = [IsSuperAdmin]

    def delete(self, request, *args, **kwargs):
        """Delete assignment by ID."""
        try:
            assignment_id = self.kwargs['pk']
            
            # Try to find and delete from wardens
            if 'warden_' in str(assignment_id):
                warden_id = int(str(assignment_id).replace('warden_', ''))
                warden = get_object_or_404(HallWarden, pk=warden_id)
                warden.delete()
            # Try to find and delete from caretakers
            elif 'caretaker_' in str(assignment_id):
                caretaker_id = int(str(assignment_id).replace('caretaker_', ''))
                caretaker = get_object_or_404(HallCaretaker, pk=caretaker_id)
                caretaker.delete()
            else:
                return Response(
                    {'error': 'Invalid assignment ID format'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            return Response(
                {'message': 'Assignment removed successfully'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


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
                        'id': faculty.id.id,  # Get the id field from ExtraInfo
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
                        'id': staff_member.id.id,  # Get the id field from ExtraInfo
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
    serializer_class = HallRoomSerializer

    def get_object(self):
        """Get room by ID."""
        room_id = self.kwargs['pk']
        return get_object_or_404(HallRoom, pk=room_id)

    def patch(self, request, *args, **kwargs):
        """
        Rename room.
        Request body: { "room_number": "A101", "block_number": "A" }
        """
        try:
            room = self.get_object()
            room_number = request.data.get('room_number')
            block_number = request.data.get('block_number')
            
            if not room_number:
                return Response(
                    {'error': 'room_number is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            updated_room = services.rename_room_in_hall(room, room_number, block_number)
            
            serializer = self.get_serializer(updated_room)
            return Response(
                {'message': 'Room renamed successfully', 'room': serializer.data},
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

    def perform_create(self, serializer):
        """Submit leave request via service."""
        try:
            services.submit_leave_request(
                student=self.request.user,
                start_date=serializer.validated_data['start_date'],
                end_date=serializer.validated_data['end_date'],
                reason=serializer.validated_data['reason'],
                destination=serializer.validated_data.get('destination'),
                contact_phone=serializer.validated_data.get('contact_phone')
            )
        except (LeaveEligibilityError, LeaveDateValidationError) as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


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
        services.approve_leave(
            leave_id=leave.id,
            approved_by=self.request.user,
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
        services.reject_leave(
            leave_id=leave.id,
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
            services.submit_complaint(
                student=self.request.user,
                category=serializer.validated_data['category'],
                title=serializer.validated_data['title'],
                description=serializer.validated_data['description'],
                priority=serializer.validated_data.get('priority'),
                location=serializer.validated_data.get('location')
            )
        except ComplaintError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


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
            resolution_notes=serializer.validated_data.get('resolution_notes')
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
        try:
            services.escalate_complaint(
                complaint_id=complaint.id,
                escalated_by=self.request.user
            )
        except ComplaintError as e:
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
# ROOM ALLOCATION VIEWS (HM-WF-103)
# ══════════════════════════════════════════════════════════════

class RoomAllocationListView(generics.ListAPIView):
    """List room allocations with pagination (50 per page) and optimized queries."""
    permission_classes = [IsAuthenticated]
    serializer_class = RoomAllocationSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        """Get allocations for user, all if staff, hall if caretaker, or student's own."""
        user = self.request.user
        if user.is_staff:
            return selectors.get_all_allocations()
        
        # Check if user is caretaker - get allocations for assigned hall
        caretaker = HallCaretaker.objects.filter(staff__id__user=user).first()
        if caretaker:
            return selectors.get_allocations_by_hall(caretaker.hall.id)
        
        # Otherwise return student's own allocations
        return selectors.get_student_allocations(user)


class RoomAllocationRetrieveView(generics.RetrieveAPIView):
    """Retrieve allocation details."""
    permission_classes = [IsAuthenticated]
    serializer_class = RoomAllocationSerializer

    def get_object(self):
        """Get allocation by ID."""
        return get_object_or_404(RoomAllocation, pk=self.kwargs['pk'])


class RoomAllocationDestroyView(generics.DestroyAPIView):
    """Delete/remove a room allocation (superadmin only)."""
    permission_classes = [IsSuperAdmin]
    serializer_class = RoomAllocationSerializer

    def get_object(self):
        """Get allocation by ID."""
        return get_object_or_404(RoomAllocation, pk=self.kwargs['pk'])
    
    def destroy(self, request, *args, **kwargs):
        """Delete allocation and release room occupancy."""
        allocation = self.get_object()
        room = allocation.room
        
        # Update room occupancy if room exists
        if room:
            room.current_occupancy = max(0, room.current_occupancy - 1)
            room.save()
        
        # Delete the allocation
        allocation.delete()
        
        return Response(
            {'detail': 'Allocation removed successfully', 'room_occupancy': room.current_occupancy if room else None},
            status=status.HTTP_200_OK
        )


class BulkRoomAllocationView(generics.CreateAPIView):
    """Perform bulk room allocation by academic batch."""
    permission_classes = [IsSuperAdmin]
    serializer_class = RoomAllocationSerializer

    def post(self, request, *args, **kwargs):
        """
        Bulk allocate rooms to students in an academic batch.
        
        Expected payload:
        {
            "academic_batch": "batch_id",
            "hall_id": "hall_id",
            "allocation_date": "YYYY-MM-DD",
            "start_room_number": 101,
            "notes": "optional notes"
        }        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            academic_batch = request.data.get('academic_batch')
            hall_id = request.data.get('hall_id')
            allocation_date = request.data.get('allocation_date')
            start_room_number = request.data.get('start_room_number', 1)
            notes = request.data.get('notes', '')
            
            logger.info(f"[BATCH_ALLOCATION] Starting allocation: batch={academic_batch}, hall={hall_id}, date={allocation_date}")
            
            if not all([academic_batch, hall_id, allocation_date]):
                return Response(
                    {'detail': 'Missing required fields: academic_batch, hall_id, allocation_date'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Verify batch exists (using Batch from programme_curriculum for admission cohorts)
            from applications.programme_curriculum.models import Batch
            batch = get_object_or_404(Batch, pk=academic_batch)
            logger.info(f"[BATCH_ALLOCATION] Found batch: {batch.name}")
            
            # Get students from batch using selector
            students = selectors.list_students_by_academic_batch(academic_batch)
            students_list = list(students)
            logger.info(f"[BATCH_ALLOCATION] Found {len(students_list)} students in batch")
            
            if not students_list:
                logger.warning(f"[BATCH_ALLOCATION] No students found in batch {academic_batch}")
                return Response(
                    {'detail': 'No students found in the specified batch'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get the hall
            hall = get_object_or_404(Hall, pk=hall_id)
            logger.info(f"[BATCH_ALLOCATION] Found hall: {hall.hall_name} (hall_id={hall.hall_id})")
            
            # Get available rooms from hall - using hall's hall_id field (not pk)
            all_available_rooms = selectors.list_available_rooms(hall.hall_id)
            rooms_list = list(all_available_rooms)
            logger.info(f"[BATCH_ALLOCATION] Found {len(rooms_list)} available rooms in hall: {[r.room_number for r in rooms_list]}")
            
            if not rooms_list:
                logger.warning(f"[BATCH_ALLOCATION] No available rooms found in hall {hall.hall_id}")
                return Response(
                    {'detail': 'No available rooms found in the specified hall'},
                    status=status.HTTP_400_BAD_REQUEST
                )
              # Prepare allocations data - allocate multiple students per room up to capacity
            allocations_data = []
            room_occupancy_tracker = {}  # Track occupancy in-memory as we allocate
            room_idx = 0
            
            for idx, student in enumerate(students_list):
                # Find next available room
                found_room = False
                while room_idx < len(rooms_list):
                    room = rooms_list[room_idx]
                    # Get current occupancy from database + tracked allocations
                    db_occupancy = selectors.count_occupied_seats_in_room(room.id)
                    tracked_allocations = room_occupancy_tracker.get(room.id, 0)
                    total_occupancy = db_occupancy + tracked_allocations
                    
                    logger.debug(f"[BATCH_ALLOCATION] Room {room.room_number}: DB={db_occupancy}, Tracked={tracked_allocations}, Total={total_occupancy}/{room.capacity}")
                    
                    if total_occupancy < room.capacity:
                        found_room = True
                        break  # Found available room
                    # Current room is full, move to next
                    room_idx += 1
                
                if not found_room:
                    logger.info(f"[BATCH_ALLOCATION] No more available rooms. Allocated {len(allocations_data)} students (stopped at student {idx}/{len(students_list)})")
                    break  # No more available rooms
                
                room = rooms_list[room_idx]
                allocations_data.append({
                    'student': student,
                    'room': room,
                    'hall': hall,
                    'allocated_by': None
                })
                # Track this allocation in memory
                room_occupancy_tracker[room.id] = room_occupancy_tracker.get(room.id, 0) + 1
                logger.debug(f"[BATCH_ALLOCATION] Allocated student {student.id.id} to room {room.room_number}")
            
            logger.info(f"[BATCH_ALLOCATION] Prepared allocations for {len(allocations_data)} students")
            
            # Perform bulk allocation using service
            result = services.bulk_allocate_rooms(room_allocations_data=allocations_data)
            logger.info(f"[BATCH_ALLOCATION] Allocation completed. Created {len(result)} allocations")
            
            return Response(
                {
                    'success': True,
                    'allocated_count': len(result),
                    'batch_id': academic_batch,
                    'hall_id': hall_id,
                    'allocations': RoomAllocationSerializer(result, many=True).data
                },
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            import traceback
            return Response(
                {
                    'detail': str(e),
                    'error_type': type(e).__name__,
                    'traceback': traceback.format_exc()
                },
                status=status.HTTP_400_BAD_REQUEST
            )


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
                current_room_id=serializer.validated_data['current_room'].id,
                requested_room_id=serializer.validated_data['requested_room'].id,
                reason=serializer.validated_data['reason']
            )
        except RoomChangeError as e:
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
        except RoomChangeError as e:
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
        except FineError as e:
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
            arrival_time=serializer.validated_data['arrival_time'],
            departure_time=serializer.validated_data['departure_time'],
            purpose=serializer.validated_data['purpose'],
            total_guests=serializer.validated_data['total_guests']
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
        
        hall = get_object_or_404(Hall, pk=hall_id)
        serializer.save(posted_by=self.request.user, hall=hall)


class NoticeRetrieveView(generics.RetrieveAPIView):
    """Retrieve a specific notice."""
    permission_classes = [IsAuthenticated]
    serializer_class = HostelNoticeBoardSerializer

    def get_object(self):
        """Get notice by ID."""
        return get_object_or_404(HostelNoticeBoard, pk=self.kwargs['pk'])