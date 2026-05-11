# Postman Collection Usage

Collection file:

```text
docs/American_TEST_full_api.postman_collection.json
```

## Before Running

1. Start the Django server:

```bash
python3 manage.py runserver 127.0.0.1:8000
```

2. Import the collection into Postman.
3. Confirm collection variables:
   - `base_url`: default `http://127.0.0.1:8000`
   - `admin_username`: default `admin`
   - `admin_password`: default `AdminPass123`
   - `signup_otp_code`: paste the signup OTP before running the OTP verification request.
   - `password_reset_otp_code`: paste the password-reset OTP before running password reset confirmation.

## Run Order

Run folders from top to bottom. The main complete scenario uses the dashboard-created student, so the OTP folder is included for endpoint coverage but is not required for the main exam/subscription flow.

The final folder, `99 Destructive Student Account Endpoints - Run Last`, changes/deletes the main student account. Keep it last.

## Notes

- The collection pre-request script creates unique phones/usernames per run and stores them as collection variables.
- Requests that upload images/files use `form-data`; optional file fields are present but disabled so the flow works without selecting local files.
- JSON requests include ready-to-run dummy data and Postman tests capture IDs/tokens for later requests.
