# Bareerah - Star Skyline Limousine WhatsApp Booking Assistant

## Overview
Bareerah is a production-ready WhatsApp AI booking assistant for Star Skyline Limousine Dubai, designed to automate the entire booking process with zero business loss. It provides a seamless, efficient, and human-like booking experience. Key capabilities include multi-language support (English, Urdu, Arabic), intelligent vehicle selection with luxury options, Google Maps-based fare calculation, support for various booking types (round-trip, multi-stop), email notifications, upsell suggestions, and robust backend API integration with fail-safe mechanisms.

## User Preferences
- Never ask about distance - calculate automatically
- Never reveal pricing formula
- Act completely human, never reveal AI
- Support point-to-point, round_trip and airport_transfer booking types
- Multi-language responses (English, Urdu, Arabic)
- Extract maximum booking details from single message
- Validate passenger/luggage against vehicle capacities
- ZERO business loss - capture every lead
- Ask for name confirmation (avoid extracting full sentences)
- Company has ONLY MALE DRIVERS - no gender questions
- Detect round-trip booking needs
- Detect & show luxury car options with models from inventory (Lexus, Mercedes, GMC, etc.)
- ElevenLabs Voice (NOW ENABLED) - Custom Bareerah voice profile (Voice ID: 4O1sYUnmtThcBoSBrri7) with Google Cloud TTS fallback
- Energetic personality: "Assalam alaikum! Main aapki travel buddy hoon! ☀️"
- Upsell attractions & packages: Suggest Burj Khalifa, Desert Safari, shopping tours

## System Architecture
Bareerah employs a fail-safe booking flow driven by a SMART NLU engine, primarily interacting via WhatsApp.

**UI/UX Decisions:**
- Conversational WhatsApp interface designed for 100% human-like interaction.
- Energetic and professional tone with appropriate use of emojis.
- Email notifications feature a professional, horizontally designed template with a purple gradient header, clear route visualization, detailed 6-column information bar, driver section, and clickable helpline.

**Technical Implementations:**
- **State Management:** Robust state persistence using PostgreSQL ensures no data loss, multi-instance safety, and resumable calls.
- **Fail-Safe NLU Engine:** GPT-4o-powered NLU extracts comprehensive booking details, manages `next_flow_step`, `updated_locked_slots`, and generates smart responses in a single call, ensuring smooth progression and preventing empty or erroneous responses.
- **Location Validation:** Utilizes Google Places API with a 120+ Dubai location fallback dictionary for rock-solid validation, ensuring no booking is lost due to location issues.
- **Fare Calculation:** Accurate fare calculation based on a backend formula: `Base Fare + max(0, Distance - Included KM) × Per KM Rate)`, with specific rates for 8 vehicle types.
- **Email Notification System:** Asynchronous, non-blocking email notifications to the team for various booking statuses (creation, pending, failure) with retry logic, triggered by both webhooks and a fallback cleanup service.
- **Voice/Audio Replies:** ElevenLabs TTS with a custom Bareerah voice profile for fresh audio generation per turn, supporting multiple languages with Google Cloud TTS as fallback.
- **Dynamic Vehicle Selection:** Fetches and auto-refreshes vehicle lists from the backend every 30 minutes, adapting to inventory changes.
- **Booking Flow Enhancements:** Includes natural driver-like flow (dropoff first), optional email collection, comprehensive address support, call-drop handling, Hindi/Urdu transliteration for names, and an improved vehicle upgrade flow.
- **Redis FAQ Cache:** A fuzzy-matched, multi-language Q&A cache handles 30+ common FAQs, reducing API calls and improving response times.
- **System Capabilities:** "Always-Create-Booking" pattern, multi-language support, JWT authenticated backend integration, dynamic vehicle synchronization, and comprehensive error handling.
- **Booking Types:** Supports point-to-point, round-trip, multi-stop, and hourly rental bookings.

**System Design Choices:**
- Prioritizes "Always-Create-Booking" to capture every lead.
- Global JWT token caching with auto-refresh for efficient backend authentication.
- Dynamic vehicle manager for scalability and zero maintenance of vehicle inventory.
- Comprehensive error handling across all modules.
- Smart Pickup/Dropoff detection using keywords and flow order.
- Per-slot location tracking with email alerts after multiple failures to prevent infinite loops.

## External Dependencies
- **WhatsApp Business API (via Twilio):** For the conversational interface.
- **GPT-4o:** For Natural Language Understanding (NLU).
- **Google Maps API:** For fare calculation and distance.
- **ElevenLabs:** For Text-to-Speech (TTS) voice replies.
- **Resend (SMTP):** For sending email notifications.
- **Star Skyline Limousine Backend API:** For booking creation, vehicle management, and JWT authentication.
- **PostgreSQL:** For persistent call state storage.
- **Redis:** For FAQ caching.