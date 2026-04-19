import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'FusionIIIT.settings')
django.setup()

from applications.academic_information.models import Student
from applications.hostel_management.models import Hostel, RoomAllotment, StudentDetails

print("Checking for allocation 4 or H-4...")

# Check RoomAllotment (Modern)
print("\n--- Modern RoomAllotment ---")
modern = RoomAllotment.objects.filter(is_active=True).all()[:5]
for m in modern:
    print(f"Student: {m.student.id.id}, Hostel: {m.hostel.hall_id}, Room: {m.room.room_number}")

# Check Academic Student (Legacy)
print("\n--- Academic Student (Legacy) ---")
academic = Student.objects.filter(hall_no__isnull=False).all()[:10]
for s in academic:
    print(f"ID: {s.id.id}, hall_no: {s.hall_no}, room_no: {s.room_no}")

# Search for any '4'
print("\n--- Search results for '4' in Academic Student ---")
search4 = Student.objects.filter(hall_no__icontains='4')
for s in search4:
    print(f"ID: {s.id.id}, hall_no: {s.hall_no}, room_no: {s.room_no}")

# Check Hostel StudentDetails
print("\n--- Hostel StudentDetails (Legacy) ---")
details = StudentDetails.objects.all()[:10]
for d in details:
    print(f"ID: {d.id}, hall_no: {d.hall_no}, room_num: {d.room_num}")

# Check Hostels
print("\n--- Hostels ---")
hostels = Hostel.objects.all()
for h in hostels:
    print(f"hall_id: {h.hall_id}, name: {h.name}")
