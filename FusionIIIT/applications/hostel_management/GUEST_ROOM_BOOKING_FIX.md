# Guest Room Booking - InsufficientRoomsError Fix

## Problem

The `create_booking` endpoint always returns `InsufficientRoomsError` with the message: "Not enough available rooms for this booking."

## Root Cause

**The `GuestRoom` table is empty!**

The `count_vacant_rooms_by_hall_and_type()` selector queries:

```python
GuestRoom.objects.filter(hall_id=hall_id, room_type=room_type, vacant=True).count()
```

If there are no `GuestRoom` records in the database, this query returns **0**, which triggers the `InsufficientRoomsError`.

## Solution

### Step 1: Add Guest Rooms to Your Database

Use the Django shell to populate guest rooms for a hall:

```bash
python manage.py shell
```

Then run:

```python
from applications.hostel_management import services
from applications.hostel_management.models import Hall

# Get a hall (example: hall with id=1)
hall_id = 1

# Create guest rooms for this hall
rooms = [
    {'room': 'G101', 'room_type': 'single'},
    {'room': 'G102', 'room_type': 'single'},
    {'room': 'G103', 'room_type': 'double'},
    {'room': 'G104', 'room_type': 'double'},
    {'room': 'G105', 'room_type': 'triple'},
    {'room': 'G106', 'room_type': 'triple'},
]

services.bulk_create_guest_rooms(hall_id=hall_id, rooms=rooms)
print("Guest rooms created successfully!")
```

### Step 2: Verify Guest Rooms Exist

Go to Django Admin and check:

1. Navigate to: `http://localhost:8000/admin/hostel_management/guestroom/`
2. You should see the guest rooms you just created
3. Make sure they have `vacant=True`

### Step 3: Test the Booking API

Now try creating a booking:

```json
POST /api/hostel-management/bookings/

{
  "hall_id": 1,
  "guest_name": "John Doe",
  "guest_phone": "9876543210",
  "guest_email": "john@example.com",
  "guest_address": "123 Main St",
  "rooms_required": 1,
  "total_guest": 1,
  "purpose": "Guest visit",
  "arrival_date": "2024-03-20",
  "arrival_time": "14:00:00",
  "departure_date": "2024-03-22",
  "departure_time": "10:00:00",
  "room_type": "single",
  "nationality": "Indian"
}
```

## Expected Results

### If Still Getting InsufficientRoomsError:

1. Check that guest rooms exist in the database for that hall
2. Check that `vacant=True` for those rooms
3. Check that `room_type` matches the request (case-sensitive: 'single', 'double', 'triple')
4. Review the debug logs:
   - The selector now logs the query results
   - Check Django logs for: "Counting vacant rooms: hall_id=..., room_type=..., count=..."

### If Successful:

The booking will be created with status `PENDING`, and you can then approve it by assigning a guest room.

## Additional Notes

- **Room Types**: Must be exactly 'single', 'double', or 'triple' (lowercase, matches `RoomType` choices)
- **Vacant Status**: Only rooms with `vacant=True` are counted as available
- **Occupied Till**: When a booking is approved, the guest room's `occupied_till` is set to the departure date
- **Bulk Creation**: Use `bulk_create_guest_rooms()` helper function to easily add rooms in bulk

## For Fixtures/Setup

Add guest rooms via Django fixture in `hostel_management/fixtures/guest_rooms.json` to auto-populate when migrations run.

## Reference

- Model: `GuestRoom` in `models.py`
- Selector: `count_vacant_rooms_by_hall_and_type()` in `selectors.py`
- Service: `bulk_create_guest_rooms()` in `services.py` (NEW)
- API View: `create_booking()` in `api/views.py`
