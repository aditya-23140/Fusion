"""
Views - Thin API views that only validate input and call services/selectors.

CRITICAL RULES:
- ZERO .objects. in this file
- ZERO business logic in this file
- Every view has @api_view, @permission_classes, @authentication_classes
- Always use DRF Response() - never HttpResponse or JsonResponse
- Always validate with serializer.is_valid() before calling services
- Each view is maximum 15 lines
"""

from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.response import Response
from rest_framework import status

from .. import selectors, services
from ..services import (
    HallNotFoundError,
    HallAlreadyExistsError,
    RoomNotAvailableError,
    RoomNotFoundError,
    StudentNotFoundError,
    StaffNotFoundError,
    FacultyNotFoundError,
    InvalidOperationError,
    AttendanceAlreadyMarkedError,
    InsufficientRoomsError,
    GuestCapacityExceededError,
    BookingNotFoundError,
    LeaveNotFoundError,
    FineNotFoundError,
    InventoryNotFoundError,
)
from .serializers import (
    HallSerializer,
    HallCreateSerializer,
    AssignCaretakerSerializer,
    AssignWardenSerializer,
    AssignBatchSerializer,
    GuestRoomBookingSerializer,
    GuestRoomBookingCreateSerializer,
    ApproveBookingSerializer,
    GuestRoomSerializer,
    StaffScheduleSerializer,
    StaffScheduleCreateSerializer,
    NoticeBoardSerializer,
    NoticeCreateSerializer,
    StudentAttendanceSerializer,
    MarkAttendanceSerializer,
    HallRoomSerializer,
    ChangeRoomSerializer,
    HostelLeaveSerializer,
    LeaveCreateSerializer,
    UpdateLeaveStatusSerializer,
    HostelComplaintSerializer,
    ComplaintCreateSerializer,
    HostelFineSerializer,
    ImposeFineSerializer,
    UpdateFineSerializer,
    HostelInventorySerializer,
    InventoryCreateSerializer,
    WorkerReportSerializer,
    TransactionHistorySerializer,
    HostelHistorySerializer,
)


# ══════════════════════════════════════════════════════════════
# HALL ENDPOINTS
# ══════════════════════════════════════════════════════════════

@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def list_halls(request):
    """List all halls."""
    halls = selectors.get_all_halls()
    serializer = HallSerializer(halls, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_hall(request, hall_id):
    """Get a specific hall by ID."""
    try:
        hall = selectors.get_hall_by_id(hall_id)
    except Exception:
        return Response({"error": "Hall not found."}, status=status.HTTP_404_NOT_FOUND)
    return Response(HallSerializer(hall).data, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_hall(request):
    """Create a new hall."""
    serializer = HallCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    try:
        hall = services.create_hall(**serializer.validated_data)
    except HallAlreadyExistsError as e:
        return Response({"error": str(e)}, status=status.HTTP_409_CONFLICT)
    return Response(HallSerializer(hall).data, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_hall(request, hall_id):
    """Delete a hall."""
    try:
        services.delete_hall(hall_id=hall_id)
    except HallNotFoundError as e:
        return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
    return Response({"message": "Hall deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


# ══════════════════════════════════════════════════════════════
# CARETAKER & WARDEN ENDPOINTS
# ══════════════════════════════════════════════════════════════

@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def assign_caretaker(request):
    """Assign a caretaker to a hall."""
    serializer = AssignCaretakerSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    try:
        services.assign_caretaker(**serializer.validated_data)
    except (HallNotFoundError, StaffNotFoundError) as e:
        return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
    return Response({"message": "Caretaker assigned successfully."}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def assign_warden(request):
    """Assign a warden to a hall."""
    serializer = AssignWardenSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    try:
        services.assign_warden(**serializer.validated_data)
    except (HallNotFoundError, FacultyNotFoundError) as e:
        return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
    return Response({"message": "Warden assigned successfully."}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def assign_batch(request):
    """Assign a batch to a hall."""
    serializer = AssignBatchSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    try:
        services.assign_batch_to_hall(**serializer.validated_data)
    except HallNotFoundError as e:
        return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
    return Response({"message": "Batch assigned successfully."}, status=status.HTTP_200_OK)


# ══════════════════════════════════════════════════════════════
# GUEST ROOM BOOKING ENDPOINTS
# ══════════════════════════════════════════════════════════════

@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_booking(request):
    """Create a guest room booking."""
    serializer = GuestRoomBookingCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    try:
        booking = services.create_guest_room_booking(intender=request.user, **serializer.validated_data)
    except (HallNotFoundError, InsufficientRoomsError, GuestCapacityExceededError) as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(GuestRoomBookingSerializer(booking).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def my_bookings(request):
    """List bookings for current user."""
    bookings = selectors.get_bookings_by_user(request.user)
    serializer = GuestRoomBookingSerializer(bookings, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def list_bookings(request):
    """List all bookings."""
    bookings = selectors.get_all_guest_room_bookings()
    serializer = GuestRoomBookingSerializer(bookings, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def approve_booking(request):
    """Approve a booking."""
    serializer = ApproveBookingSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    try:
        services.approve_guest_room_booking(**serializer.validated_data)
    except InvalidOperationError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"message": "Booking approved successfully."}, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def reject_booking(request, booking_id):
    """Reject a booking."""
    try:
        services.reject_guest_room_booking(booking_id=booking_id)
    except (BookingNotFoundError, InvalidOperationError) as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"message": "Booking rejected."}, status=status.HTTP_200_OK)


# ══════════════════════════════════════════════════════════════
# GUEST ROOM ENDPOINTS
# ══════════════════════════════════════════════════════════════

@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def list_guest_rooms(request, hall_id):
    """List vacant guest rooms for a hall."""
    hall = selectors.get_hall_by_id(hall_id)
    rooms = selectors.get_vacant_guest_rooms_by_hall(hall)
    serializer = GuestRoomSerializer(rooms, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ══════════════════════════════════════════════════════════════
# NOTICE ENDPOINTS
# ══════════════════════════════════════════════════════════════

@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_notice(request):
    """Create a notice."""
    serializer = NoticeCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    hall = selectors.get_hall_by_id(serializer.validated_data['hall_id'])
    notice = services.create_notice(hall=hall, posted_by=request.user.extrainfo, **serializer.validated_data)
    return Response(NoticeBoardSerializer(notice).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def list_notices(request):
    """List all notices."""
    notices = selectors.get_all_notices()
    serializer = NoticeBoardSerializer(notices, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_notice(request, notice_id):
    """Delete a notice."""
    services.delete_notice(notice_id=notice_id)
    return Response({"message": "Notice deleted."}, status=status.HTTP_204_NO_CONTENT)


# ══════════════════════════════════════════════════════════════
# LEAVE ENDPOINTS
# ══════════════════════════════════════════════════════════════

@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_leave(request):
    """Create leave application."""
    serializer = LeaveCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    leave = services.create_leave_application(**serializer.validated_data)
    return Response(HostelLeaveSerializer(leave).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def my_leaves(request):
    """Get leaves for current user."""
    leaves = selectors.get_leaves_by_roll_number(request.user.username)
    serializer = HostelLeaveSerializer(leaves, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def list_leaves(request):
    """List all leave applications."""
    leaves = selectors.get_all_leaves()
    serializer = HostelLeaveSerializer(leaves, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def update_leave_status(request):
    """Approve/reject leave."""
    serializer = UpdateLeaveStatusSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    try:
        services.update_leave_status(**serializer.validated_data)
    except (LeaveNotFoundError, InvalidOperationError) as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"message": "Leave status updated."}, status=status.HTTP_200_OK)


# ══════════════════════════════════════════════════════════════
# COMPLAINT ENDPOINTS
# ══════════════════════════════════════════════════════════════

@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def file_complaint(request):
    """File a complaint."""
    serializer = ComplaintCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    complaint = services.file_complaint(**serializer.validated_data)
    return Response(HostelComplaintSerializer(complaint).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def list_complaints(request):
    """List all complaints."""
    complaints = selectors.get_all_complaints()
    serializer = HostelComplaintSerializer(complaints, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def my_complaints(request):
    """Get complaints filed by current user."""
    complaints = selectors.get_complaints_by_roll_number(request.user.username)
    serializer = HostelComplaintSerializer(complaints, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ══════════════════════════════════════════════════════════════
# FINE ENDPOINTS
# ══════════════════════════════════════════════════════════════

@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def impose_fine(request):
    """Impose a fine on a student."""
    serializer = ImposeFineSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    try:
        fine = services.impose_fine(**serializer.validated_data)
    except StudentNotFoundError as e:
        return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
    return Response(HostelFineSerializer(fine).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def my_fines(request):
    """Get fines for current user."""
    fines = selectors.get_fines_by_student(request.user.username)
    serializer = HostelFineSerializer(fines, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def list_fines(request):
    """List all fines."""
    fines = selectors.get_all_fines()
    serializer = HostelFineSerializer(fines, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def update_fine(request, fine_id):
    """Update a fine."""
    serializer = UpdateFineSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    try:
        services.update_fine(fine_id=fine_id, **serializer.validated_data)
    except FineNotFoundError as e:
        return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
    return Response({"message": "Fine updated."}, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_fine(request, fine_id):
    """Delete a fine."""
    try:
        services.delete_fine(fine_id=fine_id)
    except FineNotFoundError as e:
        return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
    return Response({"message": "Fine deleted."}, status=status.HTTP_204_NO_CONTENT)


# ══════════════════════════════════════════════════════════════
# INVENTORY ENDPOINTS
# ══════════════════════════════════════════════════════════════

@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def create_inventory(request):
    """Create inventory item."""
    serializer = InventoryCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    inventory = services.create_inventory_item(**serializer.validated_data)
    return Response(HostelInventorySerializer(inventory).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def list_inventory(request, hall_id):
    """List inventory for a hall."""
    inventory = selectors.get_inventory_by_hall(hall_id)
    serializer = HostelInventorySerializer(inventory, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def update_inventory(request, inventory_id):
    """Update inventory item."""
    serializer = InventoryCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    try:
        services.update_inventory_item(inventory_id=inventory_id, **serializer.validated_data)
    except InventoryNotFoundError as e:
        return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
    return Response({"message": "Inventory updated."}, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_inventory(request, inventory_id):
    """Delete inventory item."""
    try:
        services.delete_inventory_item(inventory_id=inventory_id)
    except InventoryNotFoundError as e:
        return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
    return Response({"message": "Inventory deleted."}, status=status.HTTP_204_NO_CONTENT)


# ══════════════════════════════════════════════════════════════
# ATTENDANCE ENDPOINTS
# ══════════════════════════════════════════════════════════════

@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def mark_attendance(request):
    """Mark student attendance."""
    serializer = MarkAttendanceSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    try:
        services.mark_attendance(**serializer.validated_data)
    except (StudentNotFoundError, AttendanceAlreadyMarkedError) as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"message": "Attendance marked."}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def list_attendance(request, hall_id):
    """List attendance for a hall."""
    hall = selectors.get_hall_by_id(hall_id)
    attendance = selectors.get_attendance_by_hall(hall)
    serializer = StudentAttendanceSerializer(attendance, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ══════════════════════════════════════════════════════════════
# ROOM MANAGEMENT ENDPOINTS
# ══════════════════════════════════════════════════════════════

@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def list_rooms(request, hall_id):
    """List rooms for a hall."""
    hall = selectors.get_hall_by_id(hall_id)
    rooms = selectors.get_rooms_by_hall(hall)
    serializer = HallRoomSerializer(rooms, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def change_room(request):
    """Change student room."""
    serializer = ChangeRoomSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    try:
        services.change_student_room(**serializer.validated_data)
    except (StudentNotFoundError, RoomNotFoundError, RoomNotAvailableError) as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"message": "Room changed successfully."}, status=status.HTTP_200_OK)


# ══════════════════════════════════════════════════════════════
# HISTORY ENDPOINTS
# ══════════════════════════════════════════════════════════════

@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def list_transaction_history(request):
    """List transaction history."""
    history = selectors.get_all_transaction_history()
    serializer = TransactionHistorySerializer(history, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def list_hostel_history(request):
    """List hostel history."""
    history = selectors.get_all_hostel_history()
    serializer = HostelHistorySerializer(history, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ══════════════════════════════════════════════════════════════
# USER ROLE ENDPOINT
# ══════════════════════════════════════════════════════════════

@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_user_role(request):
    """Get the hostel role for the current user."""
    role_info = selectors.get_user_hostel_role(request.user)
    if role_info:
        return Response(role_info, status=status.HTTP_200_OK)
    return Response({"role": None, "hall": None, "hall_name": None}, status=status.HTTP_200_OK)
