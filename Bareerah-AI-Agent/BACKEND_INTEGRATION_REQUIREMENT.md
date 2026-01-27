# 🔧 BACKEND TEAM: VEHICLE ASSIGNMENT INTEGRATION

**Priority:** CRITICAL - Blocking production booking assignments  
**From:** Bareerah AI (WhatsApp Booking Assistant)  
**Date:** Nov 30, 2025  
**Status:** 🔴 FAILING - Backend schema incomplete

---

## 📊 CURRENT STATE

### What Bareerah IS Sending (✅ Working)
When a customer confirms a booking, Bareerah sends this payload to `/api/bookings/create-manual`:

```json
{
  "customer_name": "Test Bareerah",
  "customer_phone": "+971501234567",
  "customer_email": "test@email.com",
  "pickup_location": "Dubai Airport",
  "dropoff_location": "Burj Khalifa",
  "booking_type": "point_to_point",
  "vehicle_type": "SEDAN",
  "distance_km": 30,
  "passengers_count": 2,
  "luggage_count": 1,
  
  ✅ "vehicle_model": "Toyota Camry",        ← WE SEND THIS
  ✅ "assigned_vehicle_id": "VEH001"         ← WE SEND THIS
}
```

### What Backend Shows (❌ Problem)
Booking dashboard displays:
```
Vehicle Model: N/A           ← Should be "Toyota Camry"
Assigned Vehicle: None       ← Should be "VEH001"
Driver: Not assigned         ← Should have vehicle + driver info
```

---

## 🔴 THE PROBLEM

**Root Cause:** Backend bookings table schema missing two critical columns

### Missing Columns in `bookings` Table:
| Column | Type | Required | Purpose |
|--------|------|----------|---------|
| `vehicle_model` | VARCHAR(100) | ✅ YES | Car name (e.g., "Toyota Camry", "Lexus ES350") |
| `assigned_vehicle_id` | VARCHAR(50) | ✅ YES | Vehicle ID (e.g., "VEH001", "VEH007") |

### Current Schema (❌ Incomplete)
```
✅ id (UUID)
✅ customer_name
✅ customer_phone
✅ pickup_location
✅ dropoff_location
✅ vehicle_type (SEDAN, SUV, VAN, LUXURY)
✅ distance_km
✅ calculated_fare_aed
✅ service_type / booking_type
✅ number_of_passengers
✅ number_of_luggage

❌ vehicle_model ← MISSING (causes "N/A")
❌ assigned_vehicle_id ← MISSING (causes "None")
```

---

## ✅ SOLUTION - WHAT BACKEND MUST DO

### Step 1: Add Missing Columns to Database

```sql
-- Add new columns to bookings table
ALTER TABLE bookings 
ADD COLUMN vehicle_model VARCHAR(100) DEFAULT 'Not Assigned',
ADD COLUMN assigned_vehicle_id VARCHAR(50) DEFAULT NULL;

-- Optional: Add index for faster lookups
CREATE INDEX idx_assigned_vehicle_id ON bookings(assigned_vehicle_id);
```

### Step 2: Update `/api/bookings/create-manual` Endpoint

**Current API Response Issue:**
- ❌ Accepts `vehicle_model` but ignores it
- ❌ Accepts `assigned_vehicle_id` but ignores it
- ❌ Returns booking without these fields populated

**Required Fix:**

```python
# Pseudo-code for your backend
@app.post("/api/bookings/create-manual")
def create_manual_booking(payload):
    booking = Booking(
        customer_name=payload["customer_name"],
        customer_phone=payload["customer_phone"],
        customer_email=payload.get("customer_email"),
        pickup_location=payload["pickup_location"],
        dropoff_location=payload["dropoff_location"],
        booking_type=payload["booking_type"],
        vehicle_type=payload["vehicle_type"],
        
        # ✅ ADD THESE LINES - CURRENTLY MISSING
        vehicle_model=payload.get("vehicle_model", "Not Assigned"),
        assigned_vehicle_id=payload.get("assigned_vehicle_id"),
        
        distance_km=payload.get("distance_km", 0),
        passengers_count=payload.get("passengers_count", 1),
        luggage_count=payload.get("luggage_count", 0),
    )
    
    db.session.add(booking)
    db.session.commit()
    
    return {
        "success": True,
        "booking": {
            "id": booking.id,
            "vehicle_model": booking.vehicle_model,        # ← Include in response
            "assigned_vehicle_id": booking.assigned_vehicle_id  # ← Include in response
        }
    }
```

### Step 3: Update Booking Dashboard/UI

When displaying booking details, show:
```
Vehicle Model: {vehicle_model}           ← Display from DB
Assigned Vehicle: {assigned_vehicle_id}  ← Display from DB
```

---

## 🎯 TEST VALIDATION

After implementing, test with:

```bash
curl -X POST "https://your-backend.dev/api/bookings/create-manual" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "Test User",
    "customer_phone": "+971501234567",
    "pickup_location": "Dubai Airport",
    "dropoff_location": "Burj Khalifa",
    "vehicle_type": "SEDAN",
    "vehicle_model": "Toyota Camry",
    "assigned_vehicle_id": "VEH001",
    "distance_km": 25,
    "passengers_count": 2,
    "luggage_count": 1
  }'
```

Expected Response:
```json
{
  "success": true,
  "message": "Booking created successfully",
  "booking": {
    "id": "6bf9f768...",
    "vehicle_model": "Toyota Camry",      ← ✅ Should appear
    "assigned_vehicle_id": "VEH001",      ← ✅ Should appear
    "status": "IN-PROCESS"
  }
}
```

---

## 📝 VEHICLE OPTIONS BAREERAH SENDS

Fleet inventory Bareerah randomly selects from:

**Sedans:** Toyota Camry, Toyota Corolla, Honda Civic, Nissan Altima, Honda Accord  
**Luxury:** Lexus ES350, Mercedes Viano  
**SUVs:** GMC Yukon, Chevrolet Tahoe  
**Vans:** Toyota Previa, Mercedes Viano

**Vehicle IDs:** VEH001 through VEH010 (or your custom format)

---

## ⏱️ TIMELINE

- **This week:** Add columns + update endpoint
- **Thursday:** Test with Bareerah bookings
- **Friday:** Go live with vehicle assignment

---

## 📞 QUESTIONS?

If backend team needs clarification:
- Bareerah sends `vehicle_model` + `assigned_vehicle_id` on EVERY booking confirm
- Dashboard should display these instead of "N/A" and "None"
- This is blocking production deployment

**Contact:** Bareerah Integration Team
