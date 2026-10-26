# Smart Campus Resource & Room Booking System

A working beginner-friendly web application built with **Python, Flask, SQLite, HTML and CSS**.

## Features
- Student registration and login (passwords are hashed).
- Seeded resource directory (seminar hall, lab, project room, equipment).
- Booking requests with date/time validation.
- Prevents overlapping Pending or Approved bookings for the same resource.
- Student dashboard with booking status/history and pending-request cancellation.
- Admin dashboard to approve/reject requests, add resources, and activate/deactivate resources.
- Responsive, professional UI.

## Requirements
- Python 3.10 or newer recommended
- pip

## Run on macOS / Windows / Linux

1. Extract the ZIP and open the `smart_campus_booking_app` folder in VS Code.
2. Open Terminal in that folder.
3. Create a virtual environment (recommended):

   **macOS / Linux**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

   **Windows**
   ```powershell
   py -m venv .venv
   .venv\Scripts\activate
   ```

4. Install Flask:
   ```bash
   python -m pip install -r requirements.txt
   ```

5. Start the application:
   ```bash
   python app.py
   ```
   If `python` is not found on macOS, try:
   ```bash
   python3 app.py
   ```

6. Open this address in your browser:
   `http://127.0.0.1:5000`

The SQLite database file `campus_booking.db` is created automatically on first start.

## Demo administrator login
- Email: `admin@campus.local`
- Password: `Admin123!`

Use this account to approve/reject bookings and manage resources. This is a demo credential—change it before using the application beyond a local classroom demo. For a quick classroom demonstration, register a normal student account first, create a booking, then log out and log in as admin to approve it.

## How to demo
1. Register as a student.
2. Log in and submit a future booking request.
3. Try to submit an overlapping request for the same resource; the system should block it.
4. Log out and log in as admin.
5. Approve or reject the pending request.
6. Log back in as student to see the updated status.

## Notes
- This is a local academic prototype, not a production deployment.
- The app uses Flask's development server and a demo secret key by default. Do not expose it publicly as-is.
- For production, configure a strong `SECRET_KEY`, add CSRF protection, use a production WSGI server, and review authentication and database concurrency handling.
- Booking times use the computer's local time. Approved bookings are checked again by the admin before approval.
