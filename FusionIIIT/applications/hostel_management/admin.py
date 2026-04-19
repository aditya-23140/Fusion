from django.contrib import admin

from .models import *

# ══════════════════════════════════════════════════════════════
# HALL & STAFF MANAGEMENT
# ══════════════════════════════════════════════════════════════
admin.site.register(Hostel)
admin.site.register(HostelStaffAssignment)
admin.site.register(Room)

# ══════════════════════════════════════════════════════════════
# ROOM ALLOCATION & CHANGES (HM-WF-103, HM-WF-104)
# ══════════════════════════════════════════════════════════════
admin.site.register(RoomAllocationChange)
admin.site.register(RoomChangeRequest)

# ══════════════════════════════════════════════════════════════
# LEAVE MANAGEMENT (HM-WF-101)
# ══════════════════════════════════════════════════════════════
admin.site.register(HostelLeave)

# ══════════════════════════════════════════════════════════════
# COMPLAINT MANAGEMENT (HM-WF-102)
# ══════════════════════════════════════════════════════════════
admin.site.register(HostelComplaint)

# ══════════════════════════════════════════════════════════════
# FINE MANAGEMENT (HM-WF-105)
# ══════════════════════════════════════════════════════════════
admin.site.register(HostelFine)

# ══════════════════════════════════════════════════════════════
# STAFF & SCHEDULING (HM-WF-106, HM-WF-107)
# ══════════════════════════════════════════════════════════════
admin.site.register(StaffSchedule)
admin.site.register(WorkerReport)
admin.site.register(HostelAllotment)

# ══════════════════════════════════════════════════════════════
# INVENTORY MANAGEMENT (HM-WF-108)
# ══════════════════════════════════════════════════════════════
admin.site.register(HostelInventory)

# ══════════════════════════════════════════════════════════════
# NOTICE BOARD (HM-WF-110)
# ══════════════════════════════════════════════════════════════
admin.site.register(HostelNoticeBoard)

# ══════════════════════════════════════════════════════════════
# GUEST ROOM MANAGEMENT (HM-WF-112)
# ══════════════════════════════════════════════════════════════
admin.site.register(GuestRoom)
admin.site.register(GuestRoomBooking)

# ══════════════════════════════════════════════════════════════
# ATTENDANCE & RECORDS
# ══════════════════════════════════════════════════════════════
admin.site.register(HostelStudentAttendance)

# ══════════════════════════════════════════════════════════════
# STUDENT & TRANSACTION RECORDS
# ══════════════════════════════════════════════════════════════
admin.site.register(StudentDetails)
admin.site.register(HostelTransactionHistory)
admin.site.register(HostelHistory)