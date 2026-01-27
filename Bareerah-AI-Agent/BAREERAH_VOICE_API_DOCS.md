# Bareerah Voice AI - API Documentation

## Base URL
```
https://<your-replit-domain>.replit.dev
```

## 🔒 Authentication

**All Voice AI Booking endpoints require API key authentication.**

**Header Required:**
```
X-API-Key: bareerah-voice-agent-secure-2024
```

**Authentication Types:**
- **Voice AI Endpoints** (`/api/bookings/*`) - Require `X-API-Key` header
- **Admin/Vendor Endpoints** (`/api/admin/*`, `/api/vendor/*`) - Require `Authorization: Bearer <jwt_token>` header
- **Login Endpoint** (`/api/auth/login`) - No authentication required

---

## 🎤 Voice AI Booking APIs

These endpoints are designed for Bareerah's voice AI agent to call during live conversations.

**All require `X-API-Key` header.**

### 1. Calculate Fare

**Endpoint:** `POST /api/bookings/calculate-fare`

**Description:** Calculate fare for point-to-point or hourly bookings with optional discount.

**Request Body:**

**Point-to-Point Booking:**
```json
{
  "booking_type": "point",
  "vehicle_type": "Sedan",
  "distance_km": 35.5,
  "discount_percent": 0
}
```

**Hourly Booking:**
```json
{
  "booking_type": "hourly",
  "vehicle_type": "SUV",
  "hours": 3,
  "discount_percent": 10
}
```

**Vehicle Types:** `Sedan`, `SUV`, `Luxury`, `Van`, `Luxury Van`

**Response:**
```json
{
  "success": true,
  "booking_type": "point",
  "vehicle_type": "Sedan",
  "fare_before_discount": 129.25,
  "discount_amount": 12.93,
  "fare_after_discount": 116.32,
  "breakdown": "35.5 km @ AED 3.5/km = AED 124.25, Pickup fee: AED 5"
}
```

**Pricing:**
- **Point-to-point:** Distance × per_km_rate + AED 5 pickup fee
  - Sedan: AED 3.50/km
  - SUV: AED 4.50/km
  - Luxury: AED 6.50/km
- **Hourly:** Hours × hourly_rate + extra km charges + AED 5 pickup fee
  - Sedan: AED 75/hr (20 km/hr included)
  - SUV: AED 90/hr (20 km/hr included)
  - Luxury: AED 150/hr (20 km/hr included)
- **Discount:** 0-10% off fare_before_discount

---

### 2. Get Available Vehicles

**Endpoint:** `GET /api/bookings/available-vehicles?type={vehicle_type}`

**Description:** Retrieve list of available vehicles, optionally filtered by type.

**Query Parameters:**
- `type` (optional): Filter by vehicle type (sedan, suv, luxury, van)

**Example Request:**
```
GET /api/bookings/available-vehicles?type=sedan
```

**Response:**
```json
{
  "success": true,
  "count": 5,
  "vehicles": [
    {
      "id": 7,
      "model": "Toyota Camry",
      "number_plate": "Dubai B 12345",
      "vehicle_type": "sedan",
      "seats": 4,
      "driver_name": "Ahmed Raza",
      "driver_phone": "050-111-2233",
      "vendor_name": null
    },
    {
      "id": 8,
      "model": "Toyota Corolla",
      "number_plate": "Dubai C 67890",
      "vehicle_type": "sedan",
      "seats": 4,
      "driver_name": "Bilal Hussain",
      "driver_phone": "050-222-3344",
      "vendor_name": null
    }
  ]
}
```

**Notes:**
- Company fleet vehicles shown first (vendor_name is null)
- Vendor vehicles shown after company fleet
- Only vehicles with status 'available' are returned
- Maximum 10 vehicles returned

---

### 3. Create Booking

**Endpoint:** `POST /api/bookings/create-booking`

**Description:** Create a new booking after fare calculation.

**Request Body:**
```json
{
  "customer_name": "Ali Hassan",
  "customer_phone": "+971501234567",
  "pickup_location": "Dubai Marina",
  "dropoff_location": "Dubai Mall",
  "booking_type": "point",
  "distance_km": 35.5,
  "vehicle_type": "Sedan",
  "language": "en",
  "fare_before_discount": 129.25,
  "discount_percent": 10,
  "fare_after_discount": 116.32
}
```

**For Hourly Bookings:**
```json
{
  "customer_name": "Sara Ahmed",
  "customer_phone": "+971509876543",
  "pickup_location": "Jumeirah Beach Hotel",
  "dropoff_location": "",
  "booking_type": "hourly",
  "hours": 3,
  "vehicle_type": "SUV",
  "language": "ur",
  "fare_before_discount": 275.00,
  "discount_percent": 0,
  "fare_after_discount": 275.00
}
```

**Response:**
```json
{
  "success": true,
  "booking_id": 42,
  "call_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "Booking created successfully"
}
```

**Notes:**
- Creates or updates customer record by phone number
- Booking status starts as 'pending'
- Returns booking_id for vehicle assignment
- Call_id is unique identifier for tracking

---

### 4. Assign Vehicle

**Endpoint:** `POST /api/bookings/assign-vehicle`

**Description:** Assign a specific vehicle to a confirmed booking.

**Request Body:**
```json
{
  "booking_id": 42,
  "vehicle_id": 7
}
```

**Response:**
```json
{
  "success": true,
  "message": "Vehicle assigned successfully",
  "vehicle": {
    "model": "Toyota Camry",
    "plate": "Dubai B 12345",
    "driver_name": "Ahmed Raza",
    "driver_phone": "050-111-2233"
  }
}
```

**Effects:**
- Updates booking status to 'confirmed'
- Links vehicle, driver, and vendor to booking
- Changes vehicle status to 'scheduled'
- Returns complete vehicle & driver details

**Error Response (Vehicle Unavailable):**
```json
{
  "error": "Vehicle not available"
}
```

---

## 🔐 Authentication APIs

### 5. Login

**Endpoint:** `POST /api/auth/login`

**Description:** Authenticate user and receive JWT token.

**Request Body:**
```json
{
  "email": "admin@starskylimo.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "success": true,
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 1,
    "name": "System Admin",
    "email": "admin@starskylimo.com",
    "role": "admin"
  }
}
```

**Test Accounts:**
- Admin: `admin@starskylimo.com` / `password123`
- Vendor 1: `vendor1@company.com` / `password123`
- Vendor 2: `vendor2@company.com` / `password123`

---

### 6. Logout

**Endpoint:** `POST /api/auth/logout`

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Response:**
```json
{
  "success": true,
  "message": "Logged out successfully"
}
```

---

## 🎯 Conversation Flow Example

### Scenario: Point-to-Point Booking with Discount

**1. Customer:** "Marina se Dubai Mall jana hai"

**Bareerah Action:** Extract pickup (Marina) and dropoff (Dubai Mall), estimate distance

**2. Bareerah calls:**
```bash
POST /api/bookings/calculate-fare
{
  "booking_type": "point",
  "vehicle_type": "Sedan",
  "distance_km": 35.5,
  "discount_percent": 0
}
```

**Response:** AED 129.25

**3. Bareerah:** "Fare AED 129 hai for Sedan"

**4. Customer:** "Bahut zyada hai, discount milega?"

**Bareerah Action:** Apply 10% discount

**5. Bareerah calls:**
```bash
POST /api/bookings/calculate-fare
{
  "booking_type": "point",
  "vehicle_type": "Sedan",
  "distance_km": 35.5,
  "discount_percent": 10
}
```

**Response:** AED 116.32 (after 10% discount)

**6. Bareerah:** "Special 10% discount! Final fare AED 116"

**7. Customer:** "Theek hai, book karo"

**8. Bareerah calls:**
```bash
POST /api/bookings/create-booking
{
  "customer_name": "Ali Hassan",
  "customer_phone": "+971501234567",
  "pickup_location": "Dubai Marina",
  "dropoff_location": "Dubai Mall",
  "booking_type": "point",
  "distance_km": 35.5,
  "vehicle_type": "Sedan",
  "language": "ur",
  "fare_before_discount": 129.25,
  "discount_percent": 10,
  "fare_after_discount": 116.32
}
```

**Response:** booking_id: 42

**9. Bareerah:** "Booking confirmed! Would you like to see available vehicles?"

**10. Customer:** "Haan, dikhao"

**11. Bareerah calls:**
```bash
GET /api/bookings/available-vehicles?type=sedan
```

**12. Bareerah:** "We have Toyota Camry with Ahmed, or Honda Civic with Imran available"

**13. Customer:** "Camry bhej do"

**14. Bareerah calls:**
```bash
POST /api/bookings/assign-vehicle
{
  "booking_id": 42,
  "vehicle_id": 7
}
```

**15. Bareerah:** "Perfect! Toyota Camry (Dubai B 12345) with driver Ahmed Raza (050-111-2233) will pick you up from Marina!"

---

## 📊 Database Schema Reference

**Key Tables:**
- `bookings` - All ride bookings with fare, vehicle, driver info
- `customers` - Customer records (phone + name)
- `vehicles` - 16-vehicle fleet (10 company + 6 vendor)
- `drivers` - 16 drivers assigned to vehicles
- `vendors` - 2 vendor companies (Al-Sadiq, Desert Falcon)

**Booking Statuses:**
- `pending` - Created but not assigned
- `confirmed` - Vehicle assigned
- `in_progress` - Trip started
- `completed` - Trip finished
- `cancelled` - Booking cancelled

---

## 🚀 Quick Testing with cURL

**All requests require the X-API-Key header!**

**Calculate Fare (Point-to-Point):**
```bash
curl -X POST https://your-domain.replit.dev/api/bookings/calculate-fare \
  -H "Content-Type: application/json" \
  -H "X-API-Key: bareerah-voice-agent-secure-2024" \
  -d '{
    "booking_type": "point",
    "vehicle_type": "Sedan",
    "distance_km": 20
  }'
```

**Get Available Vehicles:**
```bash
curl https://your-domain.replit.dev/api/bookings/available-vehicles?type=sedan \
  -H "X-API-Key: bareerah-voice-agent-secure-2024"
```

**Create Booking:**
```bash
curl -X POST https://your-domain.replit.dev/api/bookings/create-booking \
  -H "Content-Type: application/json" \
  -H "X-API-Key: bareerah-voice-agent-secure-2024" \
  -d '{
    "customer_name": "Test User",
    "customer_phone": "+971501111111",
    "pickup_location": "Marina",
    "dropoff_location": "Mall",
    "booking_type": "point",
    "distance_km": 20,
    "vehicle_type": "Sedan",
    "language": "en",
    "fare_before_discount": 75,
    "discount_percent": 0,
    "fare_after_discount": 75
  }'
```

**Assign Vehicle:**
```bash
curl -X POST https://your-domain.replit.dev/api/bookings/assign-vehicle \
  -H "Content-Type: application/json" \
  -H "X-API-Key: bareerah-voice-agent-secure-2024" \
  -d '{
    "booking_id": 1,
    "vehicle_id": 7
  }'
```

**Test Without API Key (Should Fail):**
```bash
curl -X POST https://your-domain.replit.dev/api/bookings/calculate-fare \
  -H "Content-Type: application/json" \
  -d '{
    "booking_type": "point",
    "vehicle_type": "Sedan",
    "distance_km": 20
  }'
# Expected Response: {"error": "API key required"} with 401 status
```

---

## ✅ API Status

All endpoints are **LIVE** and **OPERATIONAL**:
- ✅ Calculate Fare (Point + Hourly)
- ✅ Get Available Vehicles
- ✅ Create Booking
- ✅ Assign Vehicle
- ✅ Authentication (Login/Logout)

**Fleet Status:** 16 vehicles available (10 company + 6 vendor)
**Database:** PostgreSQL with full relational schema
**Security:** JWT tokens, bcrypt password hashing
