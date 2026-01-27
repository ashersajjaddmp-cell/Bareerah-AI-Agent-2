# Bareerah Backend Management System (BMS) - API Reference

## ✅ Completed Features

### Database Schema (PostgreSQL)
All tables created and seeded successfully:

#### Tables Created:
1. **users** - System users (admin, vendors, drivers, customers) with JWT authentication
2. **vendors** - Vendor companies with commission management (80% default)
3. **drivers** - Driver information (16 total: 6 vendor + 10 company)
4. **vehicles** - Vehicle fleet (16 total: 6 vendor + 10 company)
5. **bookings** - Enhanced with vendor_id, vehicle_id, driver_id, booking_type, fare breakdowns
6. **payments** - Payment tracking with status and provider transaction IDs
7. **vendor_payouts** - Vendor commission and payout management
8. **audit_logs** - System action logging with JSON metadata

#### Seeded Data:
- **1 Admin User**: admin@starskylimo.com
- **2 Vendor Users**: Al-Sadiq Transport LLC, Desert Falcon Rides
- **16 Drivers**: 6 vendor drivers + 10 company fleet drivers
- **16 Vehicles**: 
  - Vendor 1 (Al-Sadiq): Toyota Innova, Hyundai Sonata, Nissan Patrol
  - Vendor 2 (Desert Falcon): Kia Carnival, Toyota Highlander, Mercedes E-Class
  - Company Fleet: 10 vehicles (Camry, Corolla, Civic, Lexus ES350, GMC Yukon, Previa, Tahoe, Altima, Accord, Viano)

### Authentication System ✅
- JWT token-based authentication (7-day expiry)
- Bcrypt password hashing
- Role-based access control (admin, vendor, driver, customer)
- Login/logout endpoints

#### Endpoints:
- `POST /api/auth/login` - User login (email + password → JWT token)
- `POST /api/auth/logout` - Logout (requires auth token)

---

## 🚧 Remaining API Endpoints to Implement

### Admin API Endpoints

#### Booking Management
- `GET /api/admin/bookings` - Get all bookings with filters (status, date range, vendor_id)
- `GET /api/admin/booking/<id>` - Get single booking details
- `POST /api/admin/booking/<id>/assign` - Assign vehicle/driver/vendor
- `POST /api/admin/booking/<id>/status` - Update booking status
- `GET /api/admin/bookings/export?format=pdf|excel` - Export bookings

#### Dashboard Statistics
- `GET /api/admin/dashboard/summary` - Revenue & booking summary (today/yesterday/week/month)
- `GET /api/admin/dashboard/revenue-chart` - 30-day revenue chart data
- `GET /api/admin/dashboard/top-vehicles` - Top 10 vehicles by bookings/revenue
- `GET /api/admin/dashboard/top-destinations` - Most popular routes
- `GET /api/admin/dashboard/top-hours` - Peak booking hours

#### Vendor Management
- `GET /api/admin/vendors` - List all vendors with revenue stats
- `POST /api/admin/vendor/<id>/commission` - Update commission percentage
- `GET /api/admin/vendors/export` - Export vendor data to Excel

#### Accounting
- `GET /api/admin/accounting/export` - Full accounting export (bookings, payments, payouts)

### Vendor Portal API Endpoints

#### Vendor Operations
- `GET /api/vendor/bookings` - Get vendor's bookings
- `GET /api/vendor/earnings` - Get vendor earnings (today/week/month with commission breakdown)
- `POST /api/vendor/vehicles` - Add new vehicle to vendor fleet
- `POST /api/vendor/drivers` - Add new driver to vendor roster

---

## 📋 Next Steps

### Phase 1: Complete Core Admin APIs
1. Add admin booking management endpoints
2. Add admin dashboard statistics endpoints
3. Add vendor management endpoints
4. Test with Postman/cURL

### Phase 2: Complete Vendor Portal APIs
1. Add vendor bookings endpoint
2. Add vendor earnings endpoint
3. Add vendor vehicle/driver management
4. Test vendor flows

### Phase 3: Build Frontend Dashboards
1. Create Admin Dashboard UI (`/admin` route)
   - Login page
   - Dashboard with charts (revenue, bookings)
   - Bookings table (filter, assign, update status)
   - Vendor management table
   - Export buttons (PDF/Excel)

2. Create Vendor Portal UI (`/vendor` route)
   - Login page
   - Earnings dashboard with commission breakdown
   - My bookings table
   - Add vehicle/driver forms

### Phase 4: Export Functionality
1. PDF generation (reportlab) for bookings reports
2. Excel generation (openpyxl) for data exports
3. Accounting export combining all financial data

### Phase 5: Integration Testing
1. Test voice booking flow → Admin dashboard visibility
2. Test admin assigns vendor vehicle → Vendor sees booking
3. Test vendor earnings calculation
4. Test export features
5. End-to-end validation

---

## 🔑 Test Credentials

### Admin Login:
- Email: `admin@starskylimo.com`
- Password: `password123`

### Vendor 1 Login:
- Email: `vendor1@company.com`
- Password: `password123`

### Vendor 2 Login:
- Email: `vendor2@company.com`
- Password: `password123`

**Note**: All accounts use bcrypt-hashed passwords. Change these in production!

---

## 💡 Implementation Notes

### Database Safety
- All DB calls use connection pool (get_db_connection/return_db_connection)
- Automatic retry on SSL errors (500ms wait)
- No parallel queries, always OPEN → EXECUTE → CLOSE pattern

### Security
- JWT tokens expire after 7 days
- Bcrypt with default rounds for password hashing
- Role-based endpoint protection via @require_auth() decorator
- Audit logging for critical actions

### Performance
- Connection pooling (1-20 connections)
- Indexed queries on foreign keys and frequently filtered columns
- Limit query results (500-1000 rows max)

---

## 📊 Database Schema Diagram

```
users (id, name, email, phone, role, password_hash)
  ├── vendors (id, user_id, company_name, commission_percent, status)
  │     ├── vehicles (id, vendor_id, plate_number, model, type, driver_id)
  │     └── bookings (id, vendor_id, vehicle_id, driver_id, customer_id, ...)
  └── drivers (id, user_id, name, phone, license_number)

bookings (id, customer_id, vendor_id, vehicle_id, driver_id, ...)
  ├── payments (id, booking_id, amount, status, provider_txn_id)
  └── customers (id, phone_number, name, gender, language)

vendor_payouts (id, vendor_id, period_start, period_end, amounts, status)

audit_logs (id, action, user_id, meta_json, created_at)
```

---

## 🎯 Current Status

**Completed**: ✅ Database schema, seed data, authentication system
**In Progress**: 🚧 Admin & Vendor API endpoints
**Pending**: ⏳ Frontend dashboards, export functionality, integration testing
