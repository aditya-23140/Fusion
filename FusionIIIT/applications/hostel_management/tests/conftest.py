"""
conftest.py — Base test setup for the hostel_management module.
Customize setUpTestData() with the model instances your API endpoints require.
"""
from django.contrib.auth.models import User
from django.test import TestCase

from applications.globals.models import ExtraInfo, HoldsDesignation, Designation, Staff, Faculty
from applications.academic_information.models import Student
from applications.hostel_management.models import (
    Hall, HallRoom, GuestRoom, HallCaretaker, HallWarden,
)


class BaseModuleTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        # Create users
        cls.student_user = User.objects.create_user(
            username='2021BCS001', password='test123'
        )
        cls.caretaker_user = User.objects.create_user(
            username='caretaker1', password='test123'
        )
        cls.warden_user = User.objects.create_user(
            username='warden1', password='test123'
        )

        # Create ExtraInfo (required by Fusion)
        cls.student_extra = ExtraInfo.objects.create(
            user=cls.student_user,
            id='2021BCS001',
            user_type='student'
        )
        cls.caretaker_extra = ExtraInfo.objects.create(
            user=cls.caretaker_user,
            id='caretaker1',
            user_type='staff'
        )
        cls.warden_extra = ExtraInfo.objects.create(
            user=cls.warden_user,
            id='warden1',
            user_type='faculty'
        )

        # Create Staff & Faculty (hostel_management FKs need these)
        cls.staff = Staff.objects.create(id=cls.caretaker_extra)
        cls.faculty = Faculty.objects.create(id=cls.warden_extra)

        # Create Student
        cls.student = Student.objects.create(
            id=cls.student_extra,
            programme='B.Tech',
            batch=2021,
            hall_no=1
        )

        # Create Designations (hostel module has role-based access)
        cls.caretaker_designation = Designation.objects.create(name='hostel_caretaker')
        HoldsDesignation.objects.create(
            user=cls.caretaker_user,
            working=cls.caretaker_user,
            designation=cls.caretaker_designation
        )
        cls.warden_designation = Designation.objects.create(name='hostel_warden')
        HoldsDesignation.objects.create(
            user=cls.warden_user,
            working=cls.warden_user,
            designation=cls.warden_designation
        )

        # Create Hall of Residence
        cls.hall = Hall.objects.create(
            hall_id='HALL1',
            hall_name='Rewa Residency',
            max_accomodation=200,
            number_students=50
        )

        # Create Rooms (needed by room allocation, room change, guest booking endpoints)
        cls.hall_room = HallRoom.objects.create(
            hall=cls.hall, room_number='A-101', block_number='A',
            capacity=1, room_type='single', status='available'
        )
        cls.guest_room = GuestRoom.objects.create(
            hall=cls.hall, room_number='G-01',
            room_type='single', capacity=1, status='available'
        )

        # Assign caretaker & warden to hall
        cls.hall_caretaker = HallCaretaker.objects.create(
            hall=cls.hall, staff=cls.staff, is_active=True
        )
        cls.hall_warden = HallWarden.objects.create(
            hall=cls.hall, faculty=cls.faculty, is_active=True
        )
