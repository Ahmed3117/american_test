# Student API Documentation

Audience: Mobile/student app developer

Source of truth: [American_TEST_full_api.postman_collection.json](American_TEST_full_api.postman_collection.json) and the latest tested Newman run [postman_full_run_report.json](postman_full_run_report.json).

Base URL variable: `{{base_url}}` (tested locally as `http://127.0.0.1:8000`).

Endpoint count in this document: **41**.

## Global Conventions

- JSON endpoints must send `Content-Type: application/json`.
- Upload endpoints use `multipart/form-data`; optional file rows are disabled in the Postman collection until a local file is selected.
- Protected endpoints use `Authorization: Bearer <access_token>`.
- Dashboard endpoints require a staff/admin token (`is_staff=True`).
- Student endpoints require a student token unless explicitly documented as signup/signin/OTP/webhook.
- Common responses: `400` validation error, `401` missing/invalid token, `403` insufficient permission/banned/blocked account, `404` object not found.
- Response examples are from the latest successful full Postman/Newman test run. IDs and timestamps are examples and will differ in another database.

## 04 Student Auth Account Basics

### 1. 01 Student Sign In
**Flow:** `04 Student Auth Account Basics`
**Method:** `POST`
**URL:** `{{base_url}}/accounts/signin/`
**Authentication:** No bearer token required
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "username": "{{student_phone}}",
  "password": "{{student_password}}",
  "device_id": "postman-device-{{scenario_suffix}}",
  "device_name": "Postman Student Device"
}
```
**Tested Response:** `200 OK`

```json
{
  "refresh": "<jwt token>",
  "access": "<jwt token>"
}
```
**Validations And Error Cases:**
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `username` and `password` are required.
- Student account must not be banned.
- Failed attempts are tracked and may create a `SecurityBlock`.
- Device token/session is created or refreshed; device limits may remove old devices.

### 2. 02 Refresh Student Token
**Flow:** `04 Student Auth Account Basics`
**Method:** `POST`
**URL:** `{{base_url}}/accounts/token/refresh/`
**Authentication:** No bearer token required; send a valid refresh token in the body
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "refresh": "{{student_refresh_token}}"
}
```
**Tested Response:** `200 OK`

```json
{
  "access": "<jwt token>"
}
```
**Validations And Error Cases:**
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `refresh` token is required.
- Invalid/expired refresh token returns `401`.

### 3. 03 Get Student Data
**Flow:** `04 Student Auth Account Basics`
**Method:** `GET`
**URL:** `{{base_url}}/accounts/get-user-data/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "id": 18,
  "username": "01095350672",
  "email": "",
  "name": "Mariam EST 95350672",
  "government": "1",
  "is_staff": false,
  "is_superuser": false,
  "user_type": "student",
  "parent_phone": "01111111111",
  "created_at": "2026-05-10T06:42:32.336728Z"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.

### 4. 04 Update Student Data
**Flow:** `04 Student Auth Account Basics`
**Method:** `PATCH`
**URL:** `{{base_url}}/accounts/update-user-data/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "name": "Mariam EST Updated {{scenario_suffix}}",
  "parent_phone": "01111111111",
  "government": "1",
  "user_type": "student"
}
```
**Tested Response:** `200 OK`

```json
{
  "id": 18,
  "username": "01095350672",
  "email": "",
  "name": "Mariam EST Updated 95350672",
  "government": "1",
  "is_staff": false,
  "is_superuser": false,
  "user_type": "student",
  "parent_phone": "01111111111",
  "created_at": "2026-05-10T06:42:32.336728Z"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Only allowed profile fields can be updated.
- Phone/username uniqueness and serializer field types are enforced.

### 5. 05 My Devices
**Flow:** `04 Student Auth Account Basics`
**Method:** `GET`
**URL:** `{{base_url}}/accounts/my-devices/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "max_allowed_devices": 2,
  "active_devices_count": 1,
  "devices": [
    {
      "id": 17,
      "device_id": "postman-device-95350672",
      "device_name": "Postman Student Device",
      "ip_address": "127.0.0.1",
      "user_agent": "PostmanRuntime/7.39.1",
      "logged_in_at": "2026-05-10T06:42:39.711746Z",
      "last_used_at": "2026-05-10T06:42:39.711770Z",
      "is_active": true,
      "is_banned": false,
      "banned_at": null,
      "ban_reason": null
    }
  ]
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- Student token must include a valid active device session unless backward-compatible old token mode applies.

## 05 Student Plans Courses Subscription Payment

### 6. 01 List Student Plans
**Flow:** `05 Student Plans Courses Subscription Payment`
**Method:** `GET`
**URL:** `{{base_url}}/plans/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 11,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "EST Spring Access",
      "price": "1500.00",
      "start_day": 1,
      "start_month": 1,
      "start_date": "01/01",
      "end_day": 31,
      "end_month": 12,
      "end_date": "31/12",
      "number_of_allowed_courses_to_subscribe": 1,
      "is_active": true,
      "has_started": true,
      "is_available_now": true
    },
    {
      "id": 2,
      "title": "EST Spring Access",
      "price": "1500.00",
      "start_day": 1,
      "start_month": 1,
      "start_date": "01/01",
      "end_day": 31,
      "end_month": 12,
      "end_date": "31/12",
      "number_of_allowed_courses_to_subscribe": 1,
      "is_active": true,
      "has_started": true,
      "is_available_now": true
    },
    {
      "id": 3,
      "title": "EST Spring Access",
      "price": "1500.00",
      "start_day": 1,
      "start_month": 1,
      "start_date": "01/01",
      "end_day": 31,
      "end_month": 12,
      "end_date": "31/12",
      "number_of_allowed_courses_to_subscribe": 1,
      "is_active": true,
      "has_started": true,
      "is_available_now": true
    },
    {
      "id": 4,
      "title": "EST Spring Access 94917534",
      "price": "1350.00",
      "start_day": 10,
      "start_month": 5,
      "start_date": "10/05",
      "end_day": 10,
      "end_month": 5,
      "end_date": "10/05",
      "number_of_allowed_courses_to_subscribe": 1,
      "is_active": true,
      "has_started": true,
      "is_available_now": true
    },
    {
      "id": 7,
      "title": "EST Spring Access 95069128",
      "price": "1350.00",
      "start_day": 10,
      "start_month": 5,
      "start_date": "10/05",
      "end_day": 10,
      "end_month": 5,
      "end_date": "10/05",
... truncated for documentation ...
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- Requires authenticated student.
- Returns all plans, including future plans; access starts only when the plan starts.

### 7. 02 Subscribe With Too Many Courses Expect 400
**Flow:** `05 Student Plans Courses Subscription Payment`
**Method:** `POST`
**URL:** `{{base_url}}/plans/{{active_plan_id}}/subscribe/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "course_ids": [
    "{{course_math_id}}",
    "{{course_english_id}}"
  ]
}
```
**Tested Response:** `400 Bad Request`

```json
{
  "course_ids": [
    "This plan allows 1 course(s)."
  ]
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `course_ids` is required and cannot be empty.
- Course count cannot exceed the plan limit.
- Courses must exist and be active.
- Plan must exist and be active/listed.

### 8. 03 Subscribe Active Plan
**Flow:** `05 Student Plans Courses Subscription Payment`
**Method:** `POST`
**URL:** `{{base_url}}/plans/{{active_plan_id}}/subscribe/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "course_ids": [
    "{{course_math_id}}"
  ]
}
```
**Tested Response:** `201 Created`

```json
{
  "id": 7,
  "plan": {
    "id": 13,
    "title": "EST Spring Access 95350672",
    "price": "1350.00",
    "start_day": 10,
    "start_month": 5,
    "start_date": "10/05",
    "end_day": 10,
    "end_month": 5,
    "end_date": "10/05",
    "number_of_allowed_courses_to_subscribe": 1,
    "is_active": true,
    "has_started": true,
    "is_available_now": true
  },
  "courses": [
    {
      "id": 16,
      "name": "EST Math 95350672",
      "description": "EST Math preparation course.",
      "image": null,
      "order": 1,
      "is_active": true,
      "units": [
        {
          "id": 13,
          "course": 16,
          "name": "Algebra Foundations",
          "description": "Core algebra skills.",
          "order": 1,
          "is_active": true
        }
      ]
    }
  ],
  "payment_status": "pending",
  "has_access_now": false,
  "easypay_invoice_uid": null,
  "easypay_invoice_sequence": null,
  "easypay_payment_url": null,
  "paid_at": null,
  "created_at": "2026-05-10T06:42:40.251314Z",
  "payment": {
    "success": false,
    "error": "EasyPay credentials are not configured."
  }
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `course_ids` is required and cannot be empty.
- Course count cannot exceed the plan limit.
- Courses must exist and be active.
- Plan must exist and be active/listed.

### 9. 04 My Subscriptions Before Payment
**Flow:** `05 Student Plans Courses Subscription Payment`
**Method:** `GET`
**URL:** `{{base_url}}/plans/my-subscriptions/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 7,
      "plan": {
        "id": 13,
        "title": "EST Spring Access 95350672",
        "price": "1350.00",
        "start_day": 10,
        "start_month": 5,
        "start_date": "10/05",
        "end_day": 10,
        "end_month": 5,
        "end_date": "10/05",
        "number_of_allowed_courses_to_subscribe": 1,
        "is_active": true,
        "has_started": true,
        "is_available_now": true
      },
      "courses": [
        {
          "id": 16,
          "name": "EST Math 95350672",
          "description": "EST Math preparation course.",
          "image": null,
          "order": 1,
          "is_active": true,
          "units": [
            {
              "id": 13,
              "course": 16,
              "name": "Algebra Foundations",
              "description": "Core algebra skills.",
              "order": 1,
              "is_active": true
            }
          ]
        }
      ],
      "payment_status": "pending",
      "has_access_now": false,
      "easypay_invoice_uid": null,
      "easypay_invoice_sequence": null,
      "easypay_payment_url": null,
      "paid_at": null,
      "created_at": "2026-05-10T06:42:40.251314Z"
    }
  ]
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- Requires authenticated student.
- Access status depends on payment status and current plan date window.

### 10. 05 List Courses Before Payment
**Flow:** `05 Student Plans Courses Subscription Payment`
**Method:** `GET`
**URL:** `{{base_url}}/courses/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 14,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "name": "EST Math - Updated",
      "description": "American Test Mathematics",
      "image": null,
      "order": 1,
      "is_active": true,
      "units": [
        {
          "id": 1,
          "course": 1,
          "name": "Algebra Foundations",
          "description": "Basic algebra",
          "order": 1,
          "is_active": true
        },
        {
          "id": 2,
          "course": 1,
          "name": "Linear Equations",
          "description": "Solving equations",
          "order": 2,
          "is_active": true
        }
      ]
    },
    {
      "id": 3,
      "name": "EST Math - Updated",
      "description": "American Test Mathematics",
      "image": null,
      "order": 1,
      "is_active": true,
      "units": [
        {
          "id": 3,
          "course": 3,
          "name": "Algebra Foundations",
          "description": "Basic algebra",
          "order": 1,
          "is_active": true
        },
        {
          "id": 4,
          "course": 3,
          "name": "Linear Equations",
          "description": "Solving equations",
          "order": 2,
          "is_active": true
        }
      ]
    },
    {
      "id": 5,
      "name": "EST Math - Updated",
      "description": "American Test Mathematics",
      "image": null,
      "order": 1,
      "is_active": true,
      "units": [
        {
          "id": 5,
          "course": 5,
          "name": "Algebra Foundations",
          "description": "Basic algebra",
          "order": 1,
          "is_active": true
        },
        {
          "id": 6,
          "course": 5,
          "name": "Linear Equations",
          "description": "Solving equations",
          "order": 2,
... truncated for documentation ...
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- Requires authenticated student.
- Course detail must reference an active/existing course.
- Course exams are empty unless the student has active paid access to that course.

### 11. 06 Course Detail Before Payment
**Flow:** `05 Student Plans Courses Subscription Payment`
**Method:** `GET`
**URL:** `{{base_url}}/courses/{{course_math_id}}/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "id": 16,
  "name": "EST Math 95350672",
  "description": "EST Math preparation course.",
  "image": null,
  "order": 1,
  "is_active": true,
  "units": [
    {
      "id": 13,
      "course": 16,
      "name": "Algebra Foundations",
      "description": "Core algebra skills.",
      "order": 1,
      "is_active": true
    }
  ]
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `404 Not Found` when a path ID does not exist.
- Requires authenticated student.
- Course detail must reference an active/existing course.
- Course exams are empty unless the student has active paid access to that course.

### 12. 07 Course Exams Before Payment Should Be Empty
**Flow:** `05 Student Plans Courses Subscription Payment`
**Method:** `GET`
**URL:** `{{base_url}}/courses/{{course_math_id}}/exams/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 0,
  "next": null,
  "previous": null,
  "results": []
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `404 Not Found` when a path ID does not exist.
- Requires authenticated student.
- Course detail must reference an active/existing course.
- Course exams are empty unless the student has active paid access to that course.

### 13. 08 Start Exam Before Payment Expect 401
**Flow:** `05 Student Plans Courses Subscription Payment`
**Method:** `GET`
**URL:** `{{base_url}}/exams/{{exam_id}}/start/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `401 Unauthorized`

```json
{
  "error": "You do not have access permissions"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `404 Not Found` when a path ID does not exist.
- Exam must exist, be active by time window, and belong to an accessible paid course.
- Student must not exceed allowed trials.
- Existing unsubmitted trials are reused/reported.

### 14. 12 My Subscriptions After Payment
**Flow:** `05 Student Plans Courses Subscription Payment`
**Method:** `GET`
**URL:** `{{base_url}}/plans/my-subscriptions/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 7,
      "plan": {
        "id": 13,
        "title": "EST Spring Access 95350672",
        "price": "1350.00",
        "start_day": 10,
        "start_month": 5,
        "start_date": "10/05",
        "end_day": 10,
        "end_month": 5,
        "end_date": "10/05",
        "number_of_allowed_courses_to_subscribe": 1,
        "is_active": true,
        "has_started": true,
        "is_available_now": true
      },
      "courses": [
        {
          "id": 16,
          "name": "EST Math 95350672",
          "description": "EST Math preparation course.",
          "image": null,
          "order": 1,
          "is_active": true,
          "units": [
            {
              "id": 13,
              "course": 16,
              "name": "Algebra Foundations",
              "description": "Core algebra skills.",
              "order": 1,
              "is_active": true
            }
          ]
        }
      ],
      "payment_status": "manual",
      "has_access_now": true,
      "easypay_invoice_uid": null,
      "easypay_invoice_sequence": null,
      "easypay_payment_url": null,
      "paid_at": "2026-05-10T06:42:40.703887Z",
      "created_at": "2026-05-10T06:42:40.251314Z"
    }
  ]
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- Requires authenticated student.
- Access status depends on payment status and current plan date window.

### 15. 13 Course Exams After Payment
**Flow:** `05 Student Plans Courses Subscription Payment`
**Method:** `GET`
**URL:** `{{base_url}}/courses/{{course_math_id}}/exams/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 22,
      "title": "EST Math Diagnostic 95350672",
      "description": "Updated diagnostic exam.",
      "number_of_questions": 3,
      "time_limit": 45,
      "score": 10.0,
      "passing_percent": 60,
      "start": "2026-05-10T05:42:36.815000Z",
      "end": "2026-05-11T06:42:36.815000Z",
      "status": "active",
      "related_name": "EST Math 95350672",
      "order": 1,
      "is_active": true,
      "show_answers_after_finish": true,
      "is_depends": false,
      "has_passed_exam": true,
      "is_favorite": false,
      "favorite_id": null
    },
    {
      "id": 23,
      "title": "Question Bank Target 95350672",
      "description": null,
      "number_of_questions": 2,
      "time_limit": 20,
      "score": 5.0,
      "passing_percent": 50,
      "start": "2026-05-10T05:42:36.919000Z",
      "end": "2026-05-11T06:42:36.919000Z",
      "status": "active",
      "related_name": "EST Math 95350672",
      "order": 2,
      "is_active": true,
      "show_answers_after_finish": false,
      "is_depends": false,
      "has_passed_exam": true,
      "is_favorite": false,
      "favorite_id": null
    },
    {
      "id": 24,
      "title": "Random Practice 95350672",
      "description": null,
      "number_of_questions": "not_calculatable",
      "time_limit": 20,
      "score": 0.0,
      "passing_percent": 50,
      "start": "2026-05-10T05:42:37.013000Z",
      "end": "2026-05-11T06:42:37.013000Z",
      "status": "active",
      "related_name": "EST Math 95350672",
      "order": 3,
      "is_active": true,
      "show_answers_after_finish": false,
      "is_depends": false,
      "has_passed_exam": true,
      "is_favorite": false,
      "favorite_id": null
    }
  ]
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `404 Not Found` when a path ID does not exist.
- Requires authenticated student.
- Course detail must reference an active/existing course.
- Course exams are empty unless the student has active paid access to that course.

### 16. 14 Unsubscribed Course Exams
**Flow:** `05 Student Plans Courses Subscription Payment`
**Method:** `GET`
**URL:** `{{base_url}}/courses/{{course_english_id}}/exams/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 0,
  "next": null,
  "previous": null,
  "results": []
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `404 Not Found` when a path ID does not exist.
- Requires authenticated student.
- Course detail must reference an active/existing course.
- Course exams are empty unless the student has active paid access to that course.

## 06 Student Course Exam Attempt

### 17. 01 Check Exam Start Ability
**Flow:** `06 Student Course Exam Attempt`
**Method:** `GET`
**URL:** `{{base_url}}/exams/{{exam_id}}/check_my_ability_to_start/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "status": "can_start"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `404 Not Found` when a path ID does not exist.
- Exam must exist, be active by time window, and belong to an accessible paid course.
- Student must not exceed allowed trials.
- Existing unsubmitted trials are reused/reported.

### 18. 02 Start Exam
**Flow:** `06 Student Course Exam Attempt`
**Method:** `GET`
**URL:** `{{base_url}}/exams/{{exam_id}}/start/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "exam_id": 22,
  "exam_title": "EST Math Diagnostic 95350672",
  "exam_time_limit": 45,
  "questions": [
    {
      "id": 25,
      "text": "Which expression equals 2(x + 5)?",
      "explanation": null,
      "image": null,
      "points": 3,
      "difficulty": "MEDIUM",
      "category": 10,
      "course": 16,
      "unit": 13,
      "is_active": true,
      "answers": [
        {
          "id": 41,
          "text": "2x + 10",
          "image": null
        },
        {
          "id": 42,
          "text": "2x + 5",
          "image": null
        }
      ],
      "question_type": "MCQ"
    },
    {
      "id": 26,
      "text": "Explain how to solve a linear equation in one variable.",
      "explanation": "Move constants to one side and divide by coefficient.",
      "image": null,
      "points": 5,
      "difficulty": "HARD",
      "category": 10,
      "course": 16,
      "unit": null,
      "is_active": true,
      "answers": [],
      "question_type": "ESSAY"
    },
    {
      "id": 24,
      "text": "If x + 3 = 7, what is x?",
      "explanation": null,
      "image": null,
      "points": 2,
      "difficulty": "EASY",
      "category": 10,
      "course": 16,
      "unit": null,
      "is_active": true,
      "answers": [
        {
          "id": 39,
          "text": "4",
          "image": null
        },
        {
          "id": 40,
          "text": "10",
          "image": null
        }
      ],
      "question_type": "MCQ"
    }
  ],
  "exam_model": null,
  "resuming": false,
  "trial_id": 8
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `404 Not Found` when a path ID does not exist.
- Exam must exist, be active by time window, and belong to an accessible paid course.
- Student must not exceed allowed trials.
- Existing unsubmitted trials are reused/reported.

### 19. 03 Submit Exam Multipart
**Flow:** `06 Student Course Exam Attempt`
**Method:** `POST`
**URL:** `{{base_url}}/exams/{{exam_id}}/submit/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** `X-Idempotency-Key: {{idempotency_key}}`
**Body Type:** `form-data`
**Body Example:**

| Key | Type | Example | Required | Notes |
|---|---|---|---|---|
| `question_id_{{q_course_id}}` | `text` | `{{q_course_id}}` | Yes/conditional |  |
| `selected_answer_id_{{q_course_id}}` | `text` | `{{q_course_correct_answer_id}}` | Yes/conditional |  |
| `question_id_{{q_unit_id}}` | `text` | `{{q_unit_id}}` | Yes/conditional |  |
| `selected_answer_id_{{q_unit_id}}` | `text` | `{{q_unit_wrong_answer_id}}` | Yes/conditional |  |
| `question_id_{{q_essay_id}}` | `text` | `{{q_essay_id}}` | Yes/conditional |  |
| `essay_answer_text_{{q_essay_id}}` | `text` | `Move constants to one side, then divide by the coefficient.` | Yes/conditional |  |
| `essay_file_{{q_essay_id}}` | `file` | `` | No | Optional file field. Enable and select a local file if you want to test uploads. |
| `submit_type` | `text` | `student_submit` | Yes/conditional |  |
**Tested Response:** `200 OK`

```json
{
  "message": "Exam submitted successfully",
  "score": 2,
  "is_succeeded": false,
  "trial": 1
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Submission must match an active started trial.
- MCQ fields use `question_id_<id>` plus `selected_answer_id_<id>`.
- Essay fields use `essay_answer_text_<id>` and optional `essay_file_<id>`.
- Selected answer must belong to the submitted question.
- Duplicate submission of an already submitted trial is rejected.

### 20. 04 Student Exam Results List
**Flow:** `06 Student Course Exam Attempt`
**Method:** `GET`
**URL:** `{{base_url}}/exams/exam-results/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "result_id": 5,
      "exam_id": 22,
      "exam_title": "EST Math Diagnostic 95350672",
      "exam_score": 10.0,
      "student_score": 2.0,
      "is_succeeded": false,
      "number_of_questions": 3,
      "allowed_to_show_result": true,
      "allowed_to_show_answers": true,
      "student_started_exam_at": "2026-05-10T06:42:41.368401Z",
      "student_submitted_exam_at": "2026-05-10T06:42:41.515491Z",
      "last_trials": [
        {
          "id": 8,
          "trial_number": 1,
          "score": 2.0,
          "exam_score": 10.0,
          "started_at": "2026-05-10T06:42:41.368401Z",
          "submitted_at": "2026-05-10T06:42:41.515491Z",
          "is_passed": false
        }
      ]
    }
  ]
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- Student can only access their own results.
- Result visibility is controlled by `allow_show_results_at`.
- Answer visibility is controlled by exam answer settings.

### 21. 05 Student Exam Result Detail
**Flow:** `06 Student Course Exam Attempt`
**Method:** `GET`
**URL:** `{{base_url}}/exams/{{exam_id}}/result/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "active_trial": 8,
  "trial_number": 1,
  "exam_id": 22,
  "exam_title": "EST Math Diagnostic 95350672",
  "exam_description": "Updated diagnostic exam.",
  "exam_score": 10.0,
  "student_score": 2.0,
  "is_succeeded": false,
  "student_trials": 1,
  "is_trials_finished": false,
  "number_of_essay": 1,
  "number_of_mcq": 2,
  "correct_mcq_count": 1,
  "incorrect_mcq_count": 1,
  "unsolved_mcq_count": 0,
  "correct_essay_count": 0,
  "incorrect_essay_count": 0,
  "unscored_essay_count": 1,
  "student_answers": [
    {
      "submission_id": 3,
      "type": "mcq",
      "question_id": 24,
      "question_category": "EST Algebra Updated 95350672",
      "question_category_id": 10,
      "question_text": "If x + 3 = 7, what is x?",
      "question_image": null,
      "question_comment": null,
      "question_explanation": null,
      "selected_answer": {
        "id": 39,
        "text": "4",
        "image": null,
        "is_correct": true
      },
      "is_correct": true,
      "is_solved": true,
      "points": 2,
      "answers": [
        {
          "id": 39,
          "text": "4",
          "image": null,
          "is_correct": true
        },
        {
          "id": 40,
          "text": "10",
          "image": null,
          "is_correct": false
        }
      ]
    },
    {
      "submission_id": 4,
      "type": "mcq",
      "question_id": 25,
      "question_category": "EST Algebra Updated 95350672",
      "question_category_id": 10,
      "question_text": "Which expression equals 2(x + 5)?",
      "question_image": null,
      "question_comment": null,
      "question_explanation": null,
      "selected_answer": {
        "id": 42,
        "text": "2x + 5",
        "image": null,
        "is_correct": false
      },
      "is_correct": false,
... truncated for documentation ...
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `404 Not Found` when a path ID does not exist.
- Student can only access their own results.
- Result visibility is controlled by `allow_show_results_at`.
- Answer visibility is controlled by exam answer settings.

### 22. 06 Student Exam Result Trial Detail
**Flow:** `06 Student Course Exam Attempt`
**Method:** `GET`
**URL:** `{{base_url}}/exams/{{exam_id}}/result/{{trial_id}}/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "active_trial": 8,
  "trial_number": 1,
  "exam_id": 22,
  "exam_title": "EST Math Diagnostic 95350672",
  "exam_description": "Updated diagnostic exam.",
  "exam_score": 10.0,
  "student_score": 2.0,
  "is_succeeded": false,
  "student_trials": 1,
  "is_trials_finished": false,
  "number_of_essay": 1,
  "number_of_mcq": 2,
  "correct_mcq_count": 1,
  "incorrect_mcq_count": 1,
  "unsolved_mcq_count": 0,
  "correct_essay_count": 0,
  "incorrect_essay_count": 0,
  "unscored_essay_count": 1,
  "student_answers": [
    {
      "submission_id": 3,
      "type": "mcq",
      "question_id": 24,
      "question_category": "EST Algebra Updated 95350672",
      "question_category_id": 10,
      "question_text": "If x + 3 = 7, what is x?",
      "question_image": null,
      "question_comment": null,
      "question_explanation": null,
      "selected_answer": {
        "id": 39,
        "text": "4",
        "image": null,
        "is_correct": true
      },
      "is_correct": true,
      "is_solved": true,
      "points": 2,
      "answers": [
        {
          "id": 39,
          "text": "4",
          "image": null,
          "is_correct": true
        },
        {
          "id": 40,
          "text": "10",
          "image": null,
          "is_correct": false
        }
      ]
    },
    {
      "submission_id": 4,
      "type": "mcq",
      "question_id": 25,
      "question_category": "EST Algebra Updated 95350672",
      "question_category_id": 10,
      "question_text": "Which expression equals 2(x + 5)?",
      "question_image": null,
      "question_comment": null,
      "question_explanation": null,
      "selected_answer": {
        "id": 42,
        "text": "2x + 5",
        "image": null,
        "is_correct": false
      },
      "is_correct": false,
... truncated for documentation ...
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `404 Not Found` when a path ID does not exist.
- Student can only access their own results.
- Result visibility is controlled by `allow_show_results_at`.
- Answer visibility is controlled by exam answer settings.

### 23. 07 Student Bank List
**Flow:** `06 Student Course Exam Attempt`
**Method:** `GET`
**URL:** `{{base_url}}/exams/student-bank/?course={{course_math_id}}`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 2,
      "question": {
        "id": 25,
        "text": "Which expression equals 2(x + 5)?",
        "explanation": null,
        "image": null,
        "points": 3,
        "difficulty": "MEDIUM",
        "category": 10,
        "course": 16,
        "unit": 13,
        "is_active": true,
        "answers": [
          {
            "id": 41,
            "text": "2x + 10",
            "image": null,
            "is_correct": true
          },
          {
            "id": 42,
            "text": "2x + 5",
            "image": null,
            "is_correct": false
          }
        ],
        "question_type": "MCQ"
      },
      "add_reason": "INCORRECT",
      "is_solved_now": false,
      "created": "2026-05-10T06:42:41.500167Z",
      "course": "16",
      "unit": "13"
    }
  ]
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- Returns the authenticated student bank only.
- Optional filters: course, unit, add_reason, is_solved_now, question__question_type.

### 24. 09 Create Temp Exam From Student Bank
**Flow:** `06 Student Course Exam Attempt`
**Method:** `POST`
**URL:** `{{base_url}}/exams/create-temp-exam/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "number_of_questions": 1,
  "course": "{{course_math_id}}",
  "selected_questions_type": "not_solved",
  "time_limit": 15
}
```
**Tested Response:** `201 Created`

```json
{
  "temp_exam_id": 1,
  "number_of_questions": 1,
  "time_limit": 15,
  "course": 16,
  "unit": null,
  "selected_questions_type": "not_solved",
  "questions": [
    {
      "id": 25,
      "text": "Which expression equals 2(x + 5)?",
      "explanation": null,
      "image": null,
      "points": 3,
      "difficulty": "MEDIUM",
      "category": 10,
      "course": 16,
      "unit": 13,
      "is_active": true,
      "answers": [
        {
          "id": 41,
          "text": "2x + 10",
          "image": null,
          "is_correct": true
        },
        {
          "id": 42,
          "text": "2x + 5",
          "image": null,
          "is_correct": false
        }
      ],
      "question_type": "MCQ"
    }
  ]
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `number_of_questions` must be a positive integer.
- `selected_questions_type` must be `solved`, `not_solved`, or null.
- Daily temp exam limit must not be exceeded.
- Student bank must contain enough active MCQ questions after filters.

### 25. 10 Submit Temp Exam Result
**Flow:** `06 Student Course Exam Attempt`
**Method:** `POST`
**URL:** `{{base_url}}/exams/submit-temp-exam-results/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "temp_exam_id": "{{temp_exam_id}}",
  "correct_question_ids": [
    "{{q_unit_id}}"
  ],
  "result": 3
}
```
**Tested Response:** `200 OK`

```json
{
  "message": "Temp exam results submitted successfully",
  "temp_exam_id": 1,
  "result": 3.0,
  "updated_questions": 1
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `temp_exam_id` is required and must belong to the student.
- `result` must be numeric when supplied.
- `correct_question_ids` marks matching student-bank questions as solved.

## 07 Student Created Exams and Admin Question Bank

### 26. 04 Exam App Admin Question Bank List
**Flow:** `07 Student Created Exams and Admin Question Bank`
**Method:** `GET`
**URL:** `{{base_url}}/exams/admin-question-bank/?question__course={{course_math_id}}`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 4,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 5,
      "question_details": {
        "id": 27,
        "text": "Which value satisfies x - 1 = 4?",
        "explanation": null,
        "image": null,
        "points": 2,
        "difficulty": "EASY",
        "category": 10,
        "course": 16,
        "unit": null,
        "is_active": true,
        "answers": [
          {
            "id": 43,
            "text": "5",
            "image": null,
            "is_correct": true
          },
          {
            "id": 44,
            "text": "3",
            "image": null,
            "is_correct": false
          }
        ],
        "question_type": "MCQ"
      },
      "question_text": "Which value satisfies x - 1 = 4?",
      "question_type": "MCQ",
      "question_points": 2,
      "question_explanation": null,
      "created": "2026-05-10T06:42:42.368774Z"
    },
    {
      "id": 4,
      "question_details": {
        "id": 26,
        "text": "Explain how to solve a linear equation in one variable.",
        "explanation": "Move constants to one side and divide by coefficient.",
        "image": null,
        "points": 5,
        "difficulty": "HARD",
        "category": 10,
        "course": 16,
        "unit": null,
        "is_active": true,
        "answers": [],
        "question_type": "ESSAY"
      },
      "question_text": "Explain how to solve a linear equation in one variable.",
      "question_type": "ESSAY",
      "question_points": 5,
      "question_explanation": "Move constants to one side and divide by coefficient.",
      "created": "2026-05-10T06:42:42.368759Z"
    },
    {
      "id": 3,
      "question_details": {
        "id": 25,
        "text": "Which expression equals 2(x + 5)?",
        "explanati
... truncated for documentation ...
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- Requires authenticated student.
- Only lists active admin-bank questions; filters by question course/unit/type.

### 27. 05 Create Student Generated Exam
**Flow:** `07 Student Created Exams and Admin Question Bank`
**Method:** `POST`
**URL:** `{{base_url}}/exams/create-student-exam/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "number_of_mcq_questions": 1,
  "number_of_essay_questions": 1,
  "course": "{{course_math_id}}",
  "time_limit": 30
}
```
**Tested Response:** `201 Created`

```json
{
  "student_exam_id": 1,
  "number_of_mcq_questions": 1,
  "number_of_essay_questions": 1,
  "time_limit": 30,
  "exam_score": 7,
  "course": 16,
  "unit": null,
  "questions": [
    {
      "id": 27,
      "text": "Which value satisfies x - 1 = 4?",
      "explanation": null,
      "image": null,
      "points": 2,
      "difficulty": "EASY",
      "category": 10,
      "course": 16,
      "unit": null,
      "is_active": true,
      "answers": [
        {
          "id": 43,
          "text": "5",
          "image": null,
          "is_correct": true
        },
        {
          "id": 44,
          "text": "3",
          "image": null,
          "is_correct": false
        }
      ],
      "question_type": "MCQ"
    },
    {
      "id": 26,
      "text": "Explain how to solve a linear equation in one variable.",
      "explanation": "Move constants to one side and divide by coefficient.",
      "image": null,
      "points": 5,
      "difficulty": "HARD",
      "category": 10,
      "course": 16,
      "unit": null,
      "is_active": true,
      "answers": [],
      "question_type": "ESSAY"
    }
  ]
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- MCQ and essay question counts must be non-negative integers and total must be greater than zero.
- Daily generated-exam limit must not be exceeded.
- Admin question bank must contain enough active questions after course/unit filters.

### 28. 06 Submit Student Generated Exam Result
**Flow:** `07 Student Created Exams and Admin Question Bank`
**Method:** `POST`
**URL:** `{{base_url}}/exams/submit-student-exam-results/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "student_exam_id": "{{student_exam_id}}",
  "result": "{{student_exam_score}}"
}
```
**Tested Response:** `200 OK`

```json
{
  "message": "Student exam results submitted successfully",
  "student_exam_id": 1,
  "result": 7.0,
  "exam_score": 7.0,
  "percentage": 100.0
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `student_exam_id` is required and must belong to the student.
- `result` is required, numeric, non-negative, and cannot exceed `exam_score`.
- Results cannot be submitted twice.

### 29. 07 List Student Generated Exams
**Flow:** `07 Student Created Exams and Admin Question Bank`
**Method:** `GET`
**URL:** `{{base_url}}/exams/student-created-exams/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "student": 13,
      "course": 16,
      "course_name": "EST Math 95350672",
      "unit": null,
      "number_of_mcq_questions": 1,
      "number_of_essay_questions": 1,
      "total_questions": 2,
      "time_limit": 30,
      "exam_score": 7.0,
      "result": 7.0,
      "percentage": 100.0,
      "created": "2026-05-10T06:42:42.622517Z"
    }
  ]
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- Returns only exams created by the authenticated student.

## 11 OTP Signup Flow - Manual OTP Variable Needed

### 30. 01 Signup Request OTP
**Flow:** `11 OTP Signup Flow - Manual OTP Variable Needed`
**Description:** This sends OTP through the configured OTP service. Put the received/generated OTP into collection variable signup_otp_code before verifying.
**Method:** `POST`
**URL:** `{{base_url}}/accounts/signup/`
**Authentication:** No bearer token required
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "username": "{{otp_student_phone}}",
  "password": "{{student_password}}",
  "name": "OTP Student {{scenario_suffix}}",
  "user_type": "student",
  "parent_phone": "01111111111",
  "government": "1"
}
```
**Tested Response:** `200 OK`

```json
{
  "success": true,
  "message": "تم إرسال رمز التحقق بنجاح",
  "phone_number": "01295350672",
  "expires_in_minutes": 10
}
```
**Validations And Error Cases:**
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Phone number/username, name, password, and student fields from the serializer are validated.
- Phone number must be unique.
- Password confirmation must match when supplied by the serializer.
- OTP send failure returns an error.

### 31. 02 Signup Resend OTP
**Flow:** `11 OTP Signup Flow - Manual OTP Variable Needed`
**Method:** `POST`
**URL:** `{{base_url}}/accounts/signup/resend-otp/`
**Authentication:** No bearer token required
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "username": "{{otp_student_phone}}"
}
```
**Tested Response:** `400 Bad Request`

```json
{
  "error": "يرجى الانتظار 119 ثانية قبل إعادة إرسال الرمز",
  "wait_time": 119,
  "max_attempts_reached": false
}
```
**Validations And Error Cases:**
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Phone number is required.
- Cooldown must pass before resend; otherwise returns `400` with `wait_time`.
- Purpose-specific resend limits/security blocks may apply.

### 32. 03 Signup Verify OTP
**Flow:** `11 OTP Signup Flow - Manual OTP Variable Needed`
**Method:** `POST`
**URL:** `{{base_url}}/accounts/signup/verify-otp/`
**Authentication:** No bearer token required
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "username": "{{otp_student_phone}}",
  "password": "{{student_password}}",
  "name": "OTP Student {{scenario_suffix}}",
  "otp_code": "{{signup_otp_code}}",
  "user_type": "student",
  "parent_phone": "01111111111",
  "government": "1",
  "device_id": "otp-device-{{scenario_suffix}}",
  "device_name": "OTP Postman Device"
}
```
**Tested Response:** `201 Created`

```json
{
  "refresh": "<jwt token>",
  "access": "<jwt token>"
}
```
**Validations And Error Cases:**
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Phone number and OTP code are required.
- OTP must exist, not be expired, not used, and match the requested purpose.
- Too many failed verification attempts may fail validation.

## 12 Password Reset Flow - Manual OTP Variable Needed

### 33. 01 Request Password Reset OTP
**Flow:** `12 Password Reset Flow - Manual OTP Variable Needed`
**Description:** Put the received/generated OTP into password_reset_otp_code before confirming.
**Method:** `POST`
**URL:** `{{base_url}}/accounts/password-reset/`
**Authentication:** No bearer token required
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "username": "{{student_phone}}"
}
```
**Tested Response:** `200 OK`

```json
{
  "success": true,
  "message": "تم إرسال رمز التحقق بنجاح",
  "expires_in_minutes": 10
}
```
**Validations And Error Cases:**
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Phone number is required and must belong to an existing user.
- Security block/cooldown rules may prevent sending OTP.

### 34. 02 Resend Password Reset OTP
**Flow:** `12 Password Reset Flow - Manual OTP Variable Needed`
**Method:** `POST`
**URL:** `{{base_url}}/accounts/password-reset/resend-otp/`
**Authentication:** No bearer token required
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "username": "{{student_phone}}"
}
```
**Tested Response:** `400 Bad Request`

```json
{
  "error": "يرجى الانتظار 119 ثانية قبل إعادة إرسال الرمز تنبيه: لديك 2 محاولة متبقية قبل حظر الحساب مؤقتًا.",
  "wait_time": 119,
  "max_attempts_reached": false,
  "remaining_attempts": 2,
  "warning": "تنبيه: لديك 2 محاولة متبقية قبل حظر الحساب مؤقتًا."
}
```
**Validations And Error Cases:**
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Phone number is required.
- Cooldown must pass before resend; otherwise returns `400` with `wait_time`.
- Purpose-specific resend limits/security blocks may apply.

### 35. 03 Confirm Password Reset
**Flow:** `12 Password Reset Flow - Manual OTP Variable Needed`
**Method:** `POST`
**URL:** `{{base_url}}/accounts/password-reset/confirm/`
**Authentication:** No bearer token required
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "username": "{{student_phone}}",
  "otp": "{{password_reset_otp_code}}",
  "new_password": "{{reset_student_password}}"
}
```
**Tested Response:** `200 OK`

```json
{
  "success": true,
  "message": "تم إعادة تعيين كلمة المرور بنجاح"
}
```
**Validations And Error Cases:**
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Phone number, OTP code, and new password are required.
- OTP must be valid for password reset.
- New password must pass password validation.

### 36. 04 Sign In After Password Reset
**Flow:** `12 Password Reset Flow - Manual OTP Variable Needed`
**Method:** `POST`
**URL:** `{{base_url}}/accounts/signin/`
**Authentication:** No bearer token required
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "username": "{{student_phone}}",
  "password": "{{reset_student_password}}",
  "device_id": "postman-reset-{{scenario_suffix}}",
  "device_name": "Postman Reset Device"
}
```
**Tested Response:** `200 OK`

```json
{
  "refresh": "<jwt token>",
  "access": "<jwt token>"
}
```
**Validations And Error Cases:**
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `username` and `password` are required.
- Student account must not be banned.
- Failed attempts are tracked and may create a `SecurityBlock`.
- Device token/session is created or refreshed; device limits may remove old devices.

## 13 Webhooks

### 37. 01 EasyPay Webhook Without API Key
**Flow:** `13 Webhooks`
**Method:** `POST`
**URL:** `{{base_url}}/api/webhook/easypay/`
**Authentication:** No bearer token required
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "invoice_uid": "{{easypay_invoice_uid}}",
  "invoice_sequence": "{{easypay_invoice_sequence}}",
  "payment_status": "paid"
}
```
**Tested Response:** `200 OK`

```json
{
  "success": true,
  "matched": false
}
```
**Validations And Error Cases:**
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Payload must be valid JSON.
- When API key URL is used, key must match the configured/shared EasyPay API key if validation is enabled.
- Unknown invoice/payment references are ignored or handled according to webhook payload matching rules.

### 38. 02 EasyPay Webhook With API Key
**Flow:** `13 Webhooks`
**Description:** Set easypay_api_key if your settings require a webhook key.
**Method:** `POST`
**URL:** `{{base_url}}/api/webhook/easypay/{{easypay_api_key}}/`
**Authentication:** No bearer token required
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "invoice_uid": "{{easypay_invoice_uid}}",
  "invoice_sequence": "{{easypay_invoice_sequence}}",
  "payment_status": "paid"
}
```
**Tested Response:** `200 OK`

```json
{
  "success": true,
  "matched": false
}
```
**Validations And Error Cases:**
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Payload must be valid JSON.
- When API key URL is used, key must match the configured/shared EasyPay API key if validation is enabled.
- Unknown invoice/payment references are ignored or handled according to webhook payload matching rules.

## 99 Destructive Student Account Endpoints - Run Last

### 39. 01 Change Student Password
**Flow:** `99 Destructive Student Account Endpoints - Run Last`
**Method:** `POST`
**URL:** `{{base_url}}/accounts/change-password/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "old_password": "{{reset_student_password}}",
  "new_password": "{{new_student_password}}"
}
```
**Tested Response:** `200 OK`

```json
{
  "message": "تم تحديث كلمة المرور بنجاح. يجب عليك تسجيل الدخول مرة أخرى"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `old_password`, `new_password`, and confirmation fields expected by the endpoint are validated.
- Old password must match current password.
- New password must pass Django password validation.

### 40. 02 Sign In After Password Change
**Flow:** `99 Destructive Student Account Endpoints - Run Last`
**Method:** `POST`
**URL:** `{{base_url}}/accounts/signin/`
**Authentication:** No bearer token required
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "username": "{{student_phone}}",
  "password": "{{new_student_password}}",
  "device_id": "postman-changed-{{scenario_suffix}}",
  "device_name": "Postman Changed Password Device"
}
```
**Tested Response:** `200 OK`

```json
{
  "refresh": "<jwt token>",
  "access": "<jwt token>"
}
```
**Validations And Error Cases:**
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `username` and `password` are required.
- Student account must not be banned.
- Failed attempts are tracked and may create a `SecurityBlock`.
- Device token/session is created or refreshed; device limits may remove old devices.

### 41. 03 Delete Own Student Account - Run Last Only
**Flow:** `99 Destructive Student Account Endpoints - Run Last`
**Description:** Destructive endpoint. Keep this as the final student request if you run it.
**Method:** `DELETE`
**URL:** `{{base_url}}/accounts/delete-account/`
**Authentication:** Bearer token: `{{student_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "message": "تم حذف الحساب بنجاح.",
  "username": "01095350672"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- Only authenticated students can delete their own account.
- Admins/staff are rejected from the student self-delete endpoint.

