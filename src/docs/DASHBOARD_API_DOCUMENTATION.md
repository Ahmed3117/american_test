# Dashboard API Documentation

Audience: Frontend dashboard developer

Source of truth: [American_TEST_full_api.postman_collection.json](American_TEST_full_api.postman_collection.json) and the latest tested Newman run [postman_full_run_report.json](postman_full_run_report.json).

Base URL variable: `{{base_url}}` (tested locally as `http://127.0.0.1:8000`).

Endpoint count in this document: **140**.

## Global Conventions

- JSON endpoints must send `Content-Type: application/json`.
- Upload endpoints use `multipart/form-data`; optional file rows are disabled in the Postman collection until a local file is selected.
- Protected endpoints use `Authorization: Bearer <access_token>`.
- Dashboard endpoints require a staff/admin token (`is_staff=True`).
- Student endpoints require a student token unless explicitly documented as signup/signin/OTP/webhook.
- Common responses: `400` validation error, `401` missing/invalid token, `403` insufficient permission/banned/blocked account, `404` object not found.
- Response examples are from the latest successful full Postman/Newman test run. IDs and timestamps are examples and will differ in another database.

## 00 Dashboard Admin Auth and User Setup

### 1. 01 Dashboard Admin Sign In
**Flow:** `00 Dashboard Admin Auth and User Setup`
**Description:** Requires an existing staff/superuser. Defaults assume local admin/admin password from the test scenario.
**Method:** `POST`
**URL:** `{{base_url}}/accounts/dashboard/signin/`
**Authentication:** No bearer token required
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "username": "{{admin_username}}",
  "password": "{{admin_password}}"
}
```
**Tested Response:** `200 OK`

```json
{
  "refresh": "<jwt token>",
  "access": "<jwt token>",
  "user": {
    "id": 1,
    "email": "admin@example.com",
    "name": "admin",
    "is_staff": true,
    "is_superuser": true
  }
}
```
**Validations And Error Cases:**
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `username` and `password` are required.
- User must be staff/admin.
- Banned accounts cannot sign in.
- Invalid credentials return `400`.

### 2. 02 Refresh Admin Token
**Flow:** `00 Dashboard Admin Auth and User Setup`
**Method:** `POST`
**URL:** `{{base_url}}/accounts/token/refresh/`
**Authentication:** No bearer token required; send a valid refresh token in the body
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "refresh": "{{admin_refresh_token}}"
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

### 3. 03 List Admins
**Flow:** `00 Dashboard Admin Auth and User Setup`
**Method:** `GET`
**URL:** `{{base_url}}/accounts/dashboard/admins/`
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
      "id": 12,
      "username": "staff_95211654",
      "email": "ops95211654@example.com",
      "name": "Operations Staff 95211654",
      "is_staff": true,
      "is_superuser": false,
      "is_banned": false,
      "banned_at": null,
      "ban_reason": "",
      "created_at": "2026-05-10T06:40:12.722835Z"
    },
    {
      "id": 7,
      "username": "staff_95069128",
      "email": "ops95069128@example.com",
      "name": "Operations Staff 95069128",
      "is_staff": true,
      "is_superuser": false,
      "is_banned": false,
      "banned_at": null,
      "ban_reason": "",
      "created_at": "2026-05-10T06:37:50.173042Z"
    },
    {
      "id": 3,
      "username": "staff_94917534",
      "email": "ops94917534@example.com",
      "name": "Operations Staff 94917534",
      "is_staff": true,
      "is_superuser": false,
      "is_banned": false,
      "banned_at": null,
      "ban_reason": "",
      "created_at": "2026-05-10T06:35:18.540357Z"
    },
    {
      "id": 1,
      "username": "admin",
      "email": "admin@example.com",
      "name": "Main Admin",
      "is_staff": true,
      "is_superuser": true,
      "is_banned": false,
      "banned_at": null,
      "ban_reason": null,
      "created_at": "2026-05-10T03:08:17.337360Z"
    }
  ]
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.

### 4. 04 Create Staff Admin
**Flow:** `00 Dashboard Admin Auth and User Setup`
**Method:** `POST`
**URL:** `{{base_url}}/accounts/dashboard/create-admin-user/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "username": "{{staff_username}}",
  "password": "{{staff_password}}",
  "name": "Operations Staff {{scenario_suffix}}",
  "email": "ops{{scenario_suffix}}@example.com",
  "user_type": "admin"
}
```
**Tested Response:** `201 Created`

```json
{
  "refresh": "<jwt token>",
  "access": "<jwt token>",
  "user": {
    "id": 17,
    "username": "staff_95350672",
    "email": "ops95350672@example.com",
    "name": "Operations Staff 95350672",
    "is_staff": true,
    "is_superuser": false,
    "is_banned": false,
    "banned_at": null,
    "ban_reason": null,
    "created_at": "2026-05-10T06:42:31.711403Z"
  }
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Only admin/staff can create dashboard admins.
- Username must be unique.
- Password and required user fields are validated.
- Created user is staff/admin.

### 5. 05 Ban Staff Admin
**Flow:** `00 Dashboard Admin Auth and User Setup`
**Method:** `POST`
**URL:** `{{base_url}}/accounts/dashboard/admins/{{staff_user_id}}/ban/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "reason": "Postman scenario ban/unban check"
}
```
**Tested Response:** `200 OK`

```json
{
  "message": "تم حظر المسؤول \"Operations Staff 95350672\" بنجاح",
  "banned_at": "2026-05-10T06:42:31.795605Z"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Target admin must exist.
- Superuser/admin permission is required.
- Ban/unban toggles account status and timestamps.

### 6. 06 Unban Staff Admin
**Flow:** `00 Dashboard Admin Auth and User Setup`
**Method:** `POST`
**URL:** `{{base_url}}/accounts/dashboard/admins/{{staff_user_id}}/unban/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "message": "تم إلغاء حظر المسؤول \"Operations Staff 95350672\" بنجاح"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Target admin must exist.
- Superuser/admin permission is required.
- Ban/unban toggles account status and timestamps.

### 7. 07 Create Main Student For Scenario
**Flow:** `00 Dashboard Admin Auth and User Setup`
**Method:** `POST`
**URL:** `{{base_url}}/accounts/dashboard/users/create/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "username": "{{student_phone}}",
  "password": "{{student_password}}",
  "name": "Mariam EST {{scenario_suffix}}",
  "user_type": "student",
  "parent_phone": "01111111111",
  "government": "1"
}
```
**Tested Response:** `201 Created`

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
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Creates a managed student user.
- Username/phone must be unique.
- Required student fields and password fields are validated.

### 8. 08 Create Managed Student For Archive Flow
**Flow:** `00 Dashboard Admin Auth and User Setup`
**Method:** `POST`
**URL:** `{{base_url}}/accounts/dashboard/users/create/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "username": "{{managed_student_phone}}",
  "password": "ManagedPass123",
  "name": "Managed Student {{scenario_suffix}}",
  "user_type": "student",
  "parent_phone": "01222222222",
  "government": "1"
}
```
**Tested Response:** `201 Created`

```json
{
  "id": 19,
  "username": "01195350672",
  "email": "",
  "name": "Managed Student 95350672",
  "government": "1",
  "is_staff": false,
  "is_superuser": false,
  "user_type": "student",
  "parent_phone": "01222222222",
  "created_at": "2026-05-10T06:42:32.850216Z"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Creates a managed student user.
- Username/phone must be unique.
- Required student fields and password fields are validated.

### 9. 09 Update Managed Student
**Flow:** `00 Dashboard Admin Auth and User Setup`
**Method:** `PATCH`
**URL:** `{{base_url}}/accounts/dashboard/users/update/{{managed_student_phone}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "name": "Managed Student Updated {{scenario_suffix}}"
}
```
**Tested Response:** `200 OK`

```json
{
  "id": 19,
  "username": "01195350672",
  "email": "",
  "name": "Managed Student Updated 95350672",
  "government": "1",
  "is_staff": false,
  "is_superuser": false,
  "user_type": "student",
  "parent_phone": "01222222222",
  "created_at": "2026-05-10T06:42:32.850216Z"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Target username must exist.
- Only serializer-allowed fields can be changed.
- Uniqueness and type validations still apply.

### 10. 10 List Dashboard Users
**Flow:** `00 Dashboard Admin Auth and User Setup`
**Method:** `GET`
**URL:** `{{base_url}}/accounts/dashboard/users/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 9,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 19,
      "username": "01195350672",
      "email": "",
      "name": "Managed Student Updated 95350672",
      "government": "1",
      "user_type": "student",
      "parent_phone": "01222222222",
      "is_banned": false,
      "banned_at": null,
      "ban_reason": null,
      "created_at": "2026-05-10T06:42:32.850216Z"
    },
    {
      "id": 18,
      "username": "01095350672",
      "email": "",
      "name": "Mariam EST 95350672",
      "government": "1",
      "user_type": "student",
      "parent_phone": "01111111111",
      "is_banned": false,
      "banned_at": null,
      "ban_reason": null,
      "created_at": "2026-05-10T06:42:32.336728Z"
    },
    {
      "id": 16,
      "username": "01295211654",
      "email": "",
      "name": "OTP Student 95211654",
      "government": "1",
      "user_type": "student",
      "parent_phone": "01111111111",
      "is_banned": false,
      "banned_at": null,
      "ban_reason": null,
      "created_at": "2026-05-10T06:40:32.369628Z"
    },
    {
      "id": 15,
      "username": "01195211654",
      "email": "",
      "name": "Managed Student Updated 95211654",
      "government": "1",
      "user_type": "student",
      "parent_phone": "01222222222",
      "is_banned": false,
      "banned_at": null,
      "ban_reason": null,
      "created_at": "2026-05-10T06:40:31.350460Z"
    },
    {
      "id": 11,
      "username": "01295069128",
      "email": "",
      "name": "OTP Student 95069128",
      "government": "1",
      "user_type": "student",
      "parent_phone": "01111111111",
      "is_banned": false,
      "banned_at": null,
      "ban_reason": null,
      "created_at": "2026-05-10T06:38:09.342663Z"
    },
    {
      "id": 10
... truncated for documentation ...
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.

### 11. 11 Get Main Student Detail
**Flow:** `00 Dashboard Admin Auth and User Setup`
**Method:** `GET`
**URL:** `{{base_url}}/accounts/dashboard/users/{{student_user_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
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
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.

## 01 Dashboard Academic Setup - Plans Courses Units

### 12. 01 Create EST Math Course
**Flow:** `01 Dashboard Academic Setup - Plans Courses Units`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/courses/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `form-data`
**Body Example:**

| Key | Type | Example | Required | Notes |
|---|---|---|---|---|
| `name` | `text` | `EST Math {{scenario_suffix}}` | Yes/conditional |  |
| `description` | `text` | `Algebra, functions, and data analysis.` | Yes/conditional |  |
| `order` | `text` | `1` | Yes/conditional |  |
| `is_active` | `text` | `true` | Yes/conditional |  |
| `image` | `file` | `` | No | Optional file field. Enable and select a local file if you want to test uploads. |
**Tested Response:** `201 Created`

```json
{
  "id": 16,
  "name": "EST Math 95350672",
  "description": "Algebra, functions, and data analysis.",
  "image": null,
  "order": 1,
  "is_active": true,
  "units": []
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Course name is required on create.
- `order` must be an integer.
- Image upload, when sent, must be a valid image file.

### 13. 02 Create EST English Course
**Flow:** `01 Dashboard Academic Setup - Plans Courses Units`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/courses/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `form-data`
**Body Example:**

| Key | Type | Example | Required | Notes |
|---|---|---|---|---|
| `name` | `text` | `EST English {{scenario_suffix}}` | Yes/conditional |  |
| `description` | `text` | `Reading and language practice.` | Yes/conditional |  |
| `order` | `text` | `2` | Yes/conditional |  |
| `is_active` | `text` | `true` | Yes/conditional |  |
| `image` | `file` | `` | No | Optional file field. Enable and select a local file if you want to test uploads. |
**Tested Response:** `201 Created`

```json
{
  "id": 17,
  "name": "EST English 95350672",
  "description": "Reading and language practice.",
  "image": null,
  "order": 2,
  "is_active": true,
  "units": []
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Course name is required on create.
- `order` must be an integer.
- Image upload, when sent, must be a valid image file.

### 14. 03 Create Throwaway Course
**Flow:** `01 Dashboard Academic Setup - Plans Courses Units`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/courses/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `form-data`
**Body Example:**

| Key | Type | Example | Required | Notes |
|---|---|---|---|---|
| `name` | `text` | `Temporary Course {{scenario_suffix}}` | Yes/conditional |  |
| `description` | `text` | `Created to test delete.` | Yes/conditional |  |
| `order` | `text` | `99` | Yes/conditional |  |
| `is_active` | `text` | `true` | Yes/conditional |  |
| `image` | `file` | `` | No | Optional file field. Enable and select a local file if you want to test uploads. |
**Tested Response:** `201 Created`

```json
{
  "id": 18,
  "name": "Temporary Course 95350672",
  "description": "Created to test delete.",
  "image": null,
  "order": 99,
  "is_active": true,
  "units": []
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Course name is required on create.
- `order` must be an integer.
- Image upload, when sent, must be a valid image file.

### 15. 04 List Dashboard Courses
**Flow:** `01 Dashboard Academic Setup - Plans Courses Units`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/courses/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 15,
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
- `403 Forbidden` when the authenticated user is not staff/admin.
- Course name is required on create.
- `order` must be an integer.
- Image upload, when sent, must be a valid image file.

### 16. 05 Get Math Course Detail
**Flow:** `01 Dashboard Academic Setup - Plans Courses Units`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/courses/{{course_math_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "id": 16,
  "name": "EST Math 95350672",
  "description": "Algebra, functions, and data analysis.",
  "image": null,
  "order": 1,
  "is_active": true,
  "units": []
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Course name is required on create.
- `order` must be an integer.
- Image upload, when sent, must be a valid image file.

### 17. 06 Update Math Course
**Flow:** `01 Dashboard Academic Setup - Plans Courses Units`
**Method:** `PATCH`
**URL:** `{{base_url}}/dashboard/courses/{{course_math_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `form-data`
**Body Example:**

| Key | Type | Example | Required | Notes |
|---|---|---|---|---|
| `description` | `text` | `EST Math preparation course.` | Yes/conditional |  |
| `image` | `file` | `` | No | Optional file field. Enable and select a local file if you want to test uploads. |
**Tested Response:** `200 OK`

```json
{
  "id": 16,
  "name": "EST Math 95350672",
  "description": "EST Math preparation course.",
  "image": null,
  "order": 1,
  "is_active": true,
  "units": []
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Course name is required on create.
- `order` must be an integer.
- Image upload, when sent, must be a valid image file.

### 18. 07 Delete Throwaway Course
**Flow:** `01 Dashboard Academic Setup - Plans Courses Units`
**Method:** `DELETE`
**URL:** `{{base_url}}/dashboard/courses/{{course_delete_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `204 No Content`

_Empty response body._
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Course name is required on create.
- `order` must be an integer.
- Image upload, when sent, must be a valid image file.

### 19. 08 Create Algebra Unit
**Flow:** `01 Dashboard Academic Setup - Plans Courses Units`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/courses/{{course_math_id}}/units/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "name": "Algebra Foundations",
  "description": "Linear equations and functions.",
  "order": 1,
  "is_active": true
}
```
**Tested Response:** `201 Created`

```json
{
  "id": 13,
  "course": 16,
  "name": "Algebra Foundations",
  "description": "Linear equations and functions.",
  "order": 1,
  "is_active": true
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Course name is required on create.
- `order` must be an integer.
- Image upload, when sent, must be a valid image file.
- Parent course must exist.
- Unit name is required on create.

### 20. 09 Create Throwaway Unit
**Flow:** `01 Dashboard Academic Setup - Plans Courses Units`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/courses/{{course_math_id}}/units/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "name": "Delete Me Unit",
  "description": "Temporary unit.",
  "order": 99,
  "is_active": true
}
```
**Tested Response:** `201 Created`

```json
{
  "id": 14,
  "course": 16,
  "name": "Delete Me Unit",
  "description": "Temporary unit.",
  "order": 99,
  "is_active": true
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Course name is required on create.
- `order` must be an integer.
- Image upload, when sent, must be a valid image file.
- Parent course must exist.
- Unit name is required on create.

### 21. 10 List Course Units
**Flow:** `01 Dashboard Academic Setup - Plans Courses Units`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/courses/{{course_math_id}}/units/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 13,
      "course": 16,
      "name": "Algebra Foundations",
      "description": "Linear equations and functions.",
      "order": 1,
      "is_active": true
    },
    {
      "id": 14,
      "course": 16,
      "name": "Delete Me Unit",
      "description": "Temporary unit.",
      "order": 99,
      "is_active": true
    }
  ]
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Course name is required on create.
- `order` must be an integer.
- Image upload, when sent, must be a valid image file.
- Parent course must exist.
- Unit name is required on create.

### 22. 11 Update Algebra Unit
**Flow:** `01 Dashboard Academic Setup - Plans Courses Units`
**Method:** `PATCH`
**URL:** `{{base_url}}/dashboard/units/{{unit_algebra_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "description": "Core algebra skills."
}
```
**Tested Response:** `200 OK`

```json
{
  "id": 13,
  "course": 16,
  "name": "Algebra Foundations",
  "description": "Core algebra skills.",
  "order": 1,
  "is_active": true
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Parent course must exist.
- Unit name is required on create.
- `order` must be an integer.

### 23. 12 Delete Throwaway Unit
**Flow:** `01 Dashboard Academic Setup - Plans Courses Units`
**Method:** `DELETE`
**URL:** `{{base_url}}/dashboard/units/{{unit_delete_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `204 No Content`

_Empty response body._
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Parent course must exist.
- Unit name is required on create.
- `order` must be an integer.

### 24. 13 Create Active Plan
**Flow:** `01 Dashboard Academic Setup - Plans Courses Units`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/plans/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "title": "EST Spring Access {{scenario_suffix}}",
  "price": "1400.00",
  "start_date": "{{active_plan_date}}",
  "end_date": "{{active_plan_date}}",
  "number_of_allowed_courses_to_subscribe": 1,
  "is_active": true
}
```
**Tested Response:** `201 Created`

```json
{
  "id": 13,
  "title": "EST Spring Access 95350672",
  "price": "1400.00",
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
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Plan dates can be sent as `DD/MM` or `DD-MM`, or as day/month fields.
- Month must be 1-12 and day must be valid for the month.
- `number_of_allowed_courses_to_subscribe` must be at least 1.
- `price` must be a valid decimal.
- Requires authenticated student.
- Returns all plans, including future plans; access starts only when the plan starts.

### 25. 14 Create Future Plan
**Flow:** `01 Dashboard Academic Setup - Plans Courses Units`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/plans/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "title": "EST Summer Access {{scenario_suffix}}",
  "price": "1800.00",
  "start_date": "{{future_plan_date}}",
  "end_date": "{{future_plan_date}}",
  "number_of_allowed_courses_to_subscribe": 2,
  "is_active": true
}
```
**Tested Response:** `201 Created`

```json
{
  "id": 14,
  "title": "EST Summer Access 95350672",
  "price": "1800.00",
  "start_day": 17,
  "start_month": 5,
  "start_date": "17/05",
  "end_day": 17,
  "end_month": 5,
  "end_date": "17/05",
  "number_of_allowed_courses_to_subscribe": 2,
  "is_active": true,
  "has_started": false,
  "is_available_now": false
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Plan dates can be sent as `DD/MM` or `DD-MM`, or as day/month fields.
- Month must be 1-12 and day must be valid for the month.
- `number_of_allowed_courses_to_subscribe` must be at least 1.
- `price` must be a valid decimal.
- Requires authenticated student.
- Returns all plans, including future plans; access starts only when the plan starts.

### 26. 15 Create Throwaway Plan
**Flow:** `01 Dashboard Academic Setup - Plans Courses Units`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/plans/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "title": "Temporary Plan {{scenario_suffix}}",
  "price": "10.00",
  "start_date": "{{active_plan_date}}",
  "end_date": "{{active_plan_date}}",
  "number_of_allowed_courses_to_subscribe": 1,
  "is_active": true
}
```
**Tested Response:** `201 Created`

```json
{
  "id": 15,
  "title": "Temporary Plan 95350672",
  "price": "10.00",
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
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Plan dates can be sent as `DD/MM` or `DD-MM`, or as day/month fields.
- Month must be 1-12 and day must be valid for the month.
- `number_of_allowed_courses_to_subscribe` must be at least 1.
- `price` must be a valid decimal.
- Requires authenticated student.
- Returns all plans, including future plans; access starts only when the plan starts.

### 27. 16 List Dashboard Plans
**Flow:** `01 Dashboard Academic Setup - Plans Courses Units`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/plans/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 12,
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
- `403 Forbidden` when the authenticated user is not staff/admin.
- Plan dates can be sent as `DD/MM` or `DD-MM`, or as day/month fields.
- Month must be 1-12 and day must be valid for the month.
- `number_of_allowed_courses_to_subscribe` must be at least 1.
- `price` must be a valid decimal.
- Requires authenticated student.
- Returns all plans, including future plans; access starts only when the plan starts.

### 28. 17 Get Active Plan Detail
**Flow:** `01 Dashboard Academic Setup - Plans Courses Units`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/plans/{{active_plan_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "id": 13,
  "title": "EST Spring Access 95350672",
  "price": "1400.00",
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
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Plan dates can be sent as `DD/MM` or `DD-MM`, or as day/month fields.
- Month must be 1-12 and day must be valid for the month.
- `number_of_allowed_courses_to_subscribe` must be at least 1.
- `price` must be a valid decimal.

### 29. 18 Update Active Plan
**Flow:** `01 Dashboard Academic Setup - Plans Courses Units`
**Method:** `PATCH`
**URL:** `{{base_url}}/dashboard/plans/{{active_plan_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "price": "1350.00"
}
```
**Tested Response:** `200 OK`

```json
{
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
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Plan dates can be sent as `DD/MM` or `DD-MM`, or as day/month fields.
- Month must be 1-12 and day must be valid for the month.
- `number_of_allowed_courses_to_subscribe` must be at least 1.
- `price` must be a valid decimal.

### 30. 19 Delete Throwaway Plan
**Flow:** `01 Dashboard Academic Setup - Plans Courses Units`
**Method:** `DELETE`
**URL:** `{{base_url}}/dashboard/plans/{{plan_delete_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `204 No Content`

_Empty response body._
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Plan dates can be sent as `DD/MM` or `DD-MM`, or as day/month fields.
- Month must be 1-12 and day must be valid for the month.
- `number_of_allowed_courses_to_subscribe` must be at least 1.
- `price` must be a valid decimal.

## 02 Dashboard Exam Setup - Categories Questions Exams

### 31. 01 Create Question Category
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/question-categories/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "title": "EST Algebra {{scenario_suffix}}"
}
```
**Tested Response:** `201 Created`

```json
{
  "id": 10,
  "title": "EST Algebra 95350672"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `title` is required on create/update.

### 32. 02 Create Throwaway Category
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/question-categories/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "title": "Delete Category {{scenario_suffix}}"
}
```
**Tested Response:** `201 Created`

```json
{
  "id": 11,
  "title": "Delete Category 95350672"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `title` is required on create/update.

### 33. 03 List Question Categories
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/question-categories/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 8,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "Algebra"
    },
    {
      "id": 2,
      "title": "Algebra"
    },
    {
      "id": 3,
      "title": "Algebra"
    },
    {
      "id": 4,
      "title": "EST Algebra Updated 94917534"
    },
    {
      "id": 6,
      "title": "EST Algebra Updated 95069128"
    },
    {
      "id": 8,
      "title": "EST Algebra Updated 95211654"
    },
    {
      "id": 10,
      "title": "EST Algebra 95350672"
    },
    {
      "id": 11,
      "title": "Delete Category 95350672"
    }
  ]
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `title` is required on create/update.

### 34. 04 Get Category Detail
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/question-categories/{{category_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "id": 10,
  "title": "EST Algebra 95350672"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `title` is required on create/update.

### 35. 05 Update Category
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `PATCH`
**URL:** `{{base_url}}/dashboard/question-categories/{{category_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "title": "EST Algebra Updated {{scenario_suffix}}"
}
```
**Tested Response:** `200 OK`

```json
{
  "id": 10,
  "title": "EST Algebra Updated 95350672"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `title` is required on create/update.

### 36. 06 Delete Throwaway Category
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `DELETE`
**URL:** `{{base_url}}/dashboard/question-categories/{{category_delete_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `204 No Content`

_Empty response body._
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `title` is required on create/update.

### 37. 07 Create Course MCQ Question
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/questions/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `form-data`
**Body Example:**

| Key | Type | Example | Required | Notes |
|---|---|---|---|---|
| `text` | `text` | `If x + 3 = 7, what is x?` | Yes/conditional |  |
| `points` | `text` | `2` | Yes/conditional |  |
| `difficulty` | `text` | `EASY` | Yes/conditional |  |
| `category` | `text` | `{{category_id}}` | Yes/conditional |  |
| `course` | `text` | `{{course_math_id}}` | Yes/conditional |  |
| `question_type` | `text` | `MCQ` | Yes/conditional |  |
| `answers[0][text]` | `text` | `4` | Yes/conditional |  |
| `answers[0][is_correct]` | `text` | `true` | Yes/conditional |  |
| `answers[1][text]` | `text` | `10` | Yes/conditional |  |
| `answers[1][is_correct]` | `text` | `false` | Yes/conditional |  |
| `image` | `file` | `` | No | Optional file field. Enable and select a local file if you want to test uploads. |
| `answers[0][image]` | `file` | `` | No | Optional file field. Enable and select a local file if you want to test uploads. |
| `answers[1][image]` | `file` | `` | No | Optional file field. Enable and select a local file if you want to test uploads. |
**Tested Response:** `201 Created`

```json
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
      "image": null,
      "is_correct": true,
      "question": 24
    },
    {
      "id": 40,
      "text": "10",
      "image": null,
      "is_correct": false,
      "question": 24
    }
  ],
  "question_type": "MCQ",
  "comment": null,
  "created": "2026-05-10T06:42:35.245138Z"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Question must relate to either a course or a unit.
- If a unit is supplied, the course is inferred from the unit.
- `question_type` must be `MCQ` or `ESSAY`.
- `difficulty` must be `EASY`, `MEDIUM`, or `HARD`.
- For multipart MCQ creation, answer keys use `answers[0][text]`, `answers[0][is_correct]`, etc.
- Image fields must be valid uploaded files when enabled.

### 38. 08 Create Unit MCQ Question
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/questions/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `form-data`
**Body Example:**

| Key | Type | Example | Required | Notes |
|---|---|---|---|---|
| `text` | `text` | `Which expression equals 2(x + 5)?` | Yes/conditional |  |
| `points` | `text` | `3` | Yes/conditional |  |
| `difficulty` | `text` | `MEDIUM` | Yes/conditional |  |
| `category` | `text` | `{{category_id}}` | Yes/conditional |  |
| `unit` | `text` | `{{unit_algebra_id}}` | Yes/conditional |  |
| `question_type` | `text` | `MCQ` | Yes/conditional |  |
| `answers[0][text]` | `text` | `2x + 10` | Yes/conditional |  |
| `answers[0][is_correct]` | `text` | `true` | Yes/conditional |  |
| `answers[1][text]` | `text` | `2x + 5` | Yes/conditional |  |
| `answers[1][is_correct]` | `text` | `false` | Yes/conditional |  |
| `image` | `file` | `` | No | Optional file field. Enable and select a local file if you want to test uploads. |
**Tested Response:** `201 Created`

```json
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
      "is_correct": true,
      "question": 25
    },
    {
      "id": 42,
      "text": "2x + 5",
      "image": null,
      "is_correct": false,
      "question": 25
    }
  ],
  "question_type": "MCQ",
  "comment": null,
  "created": "2026-05-10T06:42:35.355039Z"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Question must relate to either a course or a unit.
- If a unit is supplied, the course is inferred from the unit.
- `question_type` must be `MCQ` or `ESSAY`.
- `difficulty` must be `EASY`, `MEDIUM`, or `HARD`.
- For multipart MCQ creation, answer keys use `answers[0][text]`, `answers[0][is_correct]`, etc.
- Image fields must be valid uploaded files when enabled.

### 39. 09 Create Essay Question
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/questions/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `form-data`
**Body Example:**

| Key | Type | Example | Required | Notes |
|---|---|---|---|---|
| `text` | `text` | `Explain how to solve a linear equation in one variable.` | Yes/conditional |  |
| `points` | `text` | `5` | Yes/conditional |  |
| `difficulty` | `text` | `HARD` | Yes/conditional |  |
| `category` | `text` | `{{category_id}}` | Yes/conditional |  |
| `course` | `text` | `{{course_math_id}}` | Yes/conditional |  |
| `question_type` | `text` | `ESSAY` | Yes/conditional |  |
| `comment` | `text` | `Show clear reasoning.` | Yes/conditional |  |
| `explanation` | `text` | `Move constants to one side and divide by coefficient.` | Yes/conditional |  |
| `image` | `file` | `` | No | Optional file field. Enable and select a local file if you want to test uploads. |
**Tested Response:** `201 Created`

```json
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
  "question_type": "ESSAY",
  "comment": "Show clear reasoning.",
  "created": "2026-05-10T06:42:35.477255Z"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Question must relate to either a course or a unit.
- If a unit is supplied, the course is inferred from the unit.
- `question_type` must be `MCQ` or `ESSAY`.
- `difficulty` must be `EASY`, `MEDIUM`, or `HARD`.
- For multipart MCQ creation, answer keys use `answers[0][text]`, `answers[0][is_correct]`, etc.
- Image fields must be valid uploaded files when enabled.

### 40. 10 Create Similar MCQ Question
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/questions/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `form-data`
**Body Example:**

| Key | Type | Example | Required | Notes |
|---|---|---|---|---|
| `text` | `text` | `Which value satisfies x - 1 = 4?` | Yes/conditional |  |
| `points` | `text` | `2` | Yes/conditional |  |
| `difficulty` | `text` | `EASY` | Yes/conditional |  |
| `category` | `text` | `{{category_id}}` | Yes/conditional |  |
| `course` | `text` | `{{course_math_id}}` | Yes/conditional |  |
| `question_type` | `text` | `MCQ` | Yes/conditional |  |
| `answers[0][text]` | `text` | `5` | Yes/conditional |  |
| `answers[0][is_correct]` | `text` | `true` | Yes/conditional |  |
| `answers[1][text]` | `text` | `3` | Yes/conditional |  |
| `answers[1][is_correct]` | `text` | `false` | Yes/conditional |  |
| `image` | `file` | `` | No | Optional file field. Enable and select a local file if you want to test uploads. |
**Tested Response:** `201 Created`

```json
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
      "is_correct": true,
      "question": 27
    },
    {
      "id": 44,
      "text": "3",
      "image": null,
      "is_correct": false,
      "question": 27
    }
  ],
  "question_type": "MCQ",
  "comment": null,
  "created": "2026-05-10T06:42:35.579462Z"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Question must relate to either a course or a unit.
- If a unit is supplied, the course is inferred from the unit.
- `question_type` must be `MCQ` or `ESSAY`.
- `difficulty` must be `EASY`, `MEDIUM`, or `HARD`.
- For multipart MCQ creation, answer keys use `answers[0][text]`, `answers[0][is_correct]`, etc.
- Image fields must be valid uploaded files when enabled.

### 41. 11 Create Throwaway Question
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/questions/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `form-data`
**Body Example:**

| Key | Type | Example | Required | Notes |
|---|---|---|---|---|
| `text` | `text` | `Temporary question for delete` | Yes/conditional |  |
| `points` | `text` | `1` | Yes/conditional |  |
| `difficulty` | `text` | `EASY` | Yes/conditional |  |
| `category` | `text` | `{{category_id}}` | Yes/conditional |  |
| `course` | `text` | `{{course_math_id}}` | Yes/conditional |  |
| `question_type` | `text` | `MCQ` | Yes/conditional |  |
| `answers[0][text]` | `text` | `A` | Yes/conditional |  |
| `answers[0][is_correct]` | `text` | `true` | Yes/conditional |  |
| `answers[1][text]` | `text` | `B` | Yes/conditional |  |
| `answers[1][is_correct]` | `text` | `false` | Yes/conditional |  |
| `image` | `file` | `` | No | Optional file field. Enable and select a local file if you want to test uploads. |
**Tested Response:** `201 Created`

```json
{
  "id": 28,
  "text": "Temporary question for delete",
  "explanation": null,
  "image": null,
  "points": 1,
  "difficulty": "EASY",
  "category": 10,
  "course": 16,
  "unit": null,
  "is_active": true,
  "answers": [
    {
      "id": 45,
      "text": "A",
      "image": null,
      "is_correct": true,
      "question": 28
    },
    {
      "id": 46,
      "text": "B",
      "image": null,
      "is_correct": false,
      "question": 28
    }
  ],
  "question_type": "MCQ",
  "comment": null,
  "created": "2026-05-10T06:42:35.705265Z"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Question must relate to either a course or a unit.
- If a unit is supplied, the course is inferred from the unit.
- `question_type` must be `MCQ` or `ESSAY`.
- `difficulty` must be `EASY`, `MEDIUM`, or `HARD`.
- For multipart MCQ creation, answer keys use `answers[0][text]`, `answers[0][is_correct]`, etc.
- Image fields must be valid uploaded files when enabled.

### 42. 12 List Questions
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/questions/?course={{course_math_id}}`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 28,
      "text": "Temporary question for delete",
      "explanation": null,
      "image": null,
      "points": 1,
      "difficulty": "EASY",
      "category": 10,
      "course": 16,
      "unit": null,
      "is_active": true,
      "answers": [
        {
          "id": 45,
          "text": "A",
          "image": null,
          "is_correct": true,
          "question": 28
        },
        {
          "id": 46,
          "text": "B",
          "image": null,
          "is_correct": false,
          "question": 28
        }
      ],
      "question_type": "MCQ",
      "comment": null,
      "created": "2026-05-10T06:42:35.705265Z"
    },
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
          "is_correct": true,
          "question": 27
        },
        {
          "id": 44,
          "text": "3",
          "image": null,
          "is_correct": false,
          "question": 27
        }
      ],
      "question_type": "MCQ",
      "comment": null,
      "created": "2026-05-10T06:42:35.579462Z"
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
      "question_type": "ESSAY",
... truncated for documentation ...
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- Question must relate to either a course or a unit.
- If a unit is supplied, the course is inferred from the unit.
- `question_type` must be `MCQ` or `ESSAY`.
- `difficulty` must be `EASY`, `MEDIUM`, or `HARD`.
- For multipart MCQ creation, answer keys use `answers[0][text]`, `answers[0][is_correct]`, etc.
- Image fields must be valid uploaded files when enabled.

### 43. 13 Get Course Question Detail
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/questions/{{q_course_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
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
      "image": null,
      "is_correct": true,
      "question": 24
    },
    {
      "id": 40,
      "text": "10",
      "image": null,
      "is_correct": false,
      "question": 24
    }
  ],
  "question_type": "MCQ",
  "comment": null,
  "created": "2026-05-10T06:42:35.245138Z"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Question must relate to either a course or a unit.
- If a unit is supplied, the course is inferred from the unit.
- `question_type` must be `MCQ` or `ESSAY`.
- `difficulty` must be `EASY`, `MEDIUM`, or `HARD`.
- For multipart MCQ creation, answer keys use `answers[0][text]`, `answers[0][is_correct]`, etc.
- Image fields must be valid uploaded files when enabled.

### 44. 14 Update Similar Question
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `PATCH`
**URL:** `{{base_url}}/dashboard/questions/{{q_similar_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `form-data`
**Body Example:**

| Key | Type | Example | Required | Notes |
|---|---|---|---|---|
| `comment` | `text` | `reviewed by Postman` | Yes/conditional |  |
| `image` | `file` | `` | No | Optional file field. Enable and select a local file if you want to test uploads. |
**Tested Response:** `200 OK`

```json
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
      "is_correct": true,
      "question": 27
    },
    {
      "id": 44,
      "text": "3",
      "image": null,
      "is_correct": false,
      "question": 27
    }
  ],
  "question_type": "MCQ",
  "comment": "reviewed by Postman",
  "created": "2026-05-10T06:42:35.579462Z"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Question must relate to either a course or a unit.
- If a unit is supplied, the course is inferred from the unit.
- `question_type` must be `MCQ` or `ESSAY`.
- `difficulty` must be `EASY`, `MEDIUM`, or `HARD`.
- For multipart MCQ creation, answer keys use `answers[0][text]`, `answers[0][is_correct]`, etc.
- Image fields must be valid uploaded files when enabled.

### 45. 15 Delete Throwaway Question
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `DELETE`
**URL:** `{{base_url}}/dashboard/questions/{{q_delete_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `204 No Content`

_Empty response body._
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Question must relate to either a course or a unit.
- If a unit is supplied, the course is inferred from the unit.
- `question_type` must be `MCQ` or `ESSAY`.
- `difficulty` must be `EASY`, `MEDIUM`, or `HARD`.
- For multipart MCQ creation, answer keys use `answers[0][text]`, `answers[0][is_correct]`, etc.
- Image fields must be valid uploaded files when enabled.

### 46. 16 Bulk Create Question And Link To Exam Later
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/questions/bulk/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `form-data`
**Body Example:**

| Key | Type | Example | Required | Notes |
|---|---|---|---|---|
| `questions[0][text]` | `text` | `Bulk-created algebra question` | Yes/conditional |  |
| `questions[0][points]` | `text` | `2` | Yes/conditional |  |
| `questions[0][difficulty]` | `text` | `EASY` | Yes/conditional |  |
| `questions[0][category]` | `text` | `{{category_id}}` | Yes/conditional |  |
| `questions[0][course]` | `text` | `{{course_math_id}}` | Yes/conditional |  |
| `questions[0][question_type]` | `text` | `MCQ` | Yes/conditional |  |
| `questions[0][answers][0][text]` | `text` | `Correct` | Yes/conditional |  |
| `questions[0][answers][0][is_correct]` | `text` | `true` | Yes/conditional |  |
| `questions[0][answers][1][text]` | `text` | `Wrong` | Yes/conditional |  |
| `questions[0][answers][1][is_correct]` | `text` | `false` | Yes/conditional |  |
| `questions[0][image]` | `file` | `` | No | Optional file field. Enable and select a local file if you want to test uploads. |
**Tested Response:** `201 Created`

```json
[
  {
    "id": 29,
    "text": "Bulk-created algebra question",
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
        "id": 47,
        "text": "Correct",
        "image": null,
        "is_correct": true,
        "question": 29
      },
      {
        "id": 48,
        "text": "Wrong",
        "image": null,
        "is_correct": false,
        "question": 29
      }
    ],
    "question_type": "MCQ",
    "comment": null,
    "created": "2026-05-10T06:42:36.109822Z"
  }
]
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Each `questions[i]` item must include valid question fields.
- Optional `exam_id` must reference an existing exam if used.
- Nested answers are validated per answer.

### 47. 16A Bulk Create Question Alias Endpoint
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/questions/bulk-create/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `form-data`
**Body Example:**

| Key | Type | Example | Required | Notes |
|---|---|---|---|---|
| `questions[0][text]` | `text` | `Bulk-create alias question` | Yes/conditional |  |
| `questions[0][points]` | `text` | `1` | Yes/conditional |  |
| `questions[0][difficulty]` | `text` | `EASY` | Yes/conditional |  |
| `questions[0][category]` | `text` | `{{category_id}}` | Yes/conditional |  |
| `questions[0][course]` | `text` | `{{course_math_id}}` | Yes/conditional |  |
| `questions[0][question_type]` | `text` | `MCQ` | Yes/conditional |  |
| `questions[0][answers][0][text]` | `text` | `Correct` | Yes/conditional |  |
| `questions[0][answers][0][is_correct]` | `text` | `true` | Yes/conditional |  |
| `questions[0][answers][1][text]` | `text` | `Wrong` | Yes/conditional |  |
| `questions[0][answers][1][is_correct]` | `text` | `false` | Yes/conditional |  |
| `questions[0][image]` | `file` | `` | No | Optional file field. Enable and select a local file if you want to test uploads. |
**Tested Response:** `201 Created`

```json
[
  {
    "id": 30,
    "text": "Bulk-create alias question",
    "explanation": null,
    "image": null,
    "points": 1,
    "difficulty": "EASY",
    "category": 10,
    "course": 16,
    "unit": null,
    "is_active": true,
    "answers": [
      {
        "id": 49,
        "text": "Correct",
        "image": null,
        "is_correct": true,
        "question": 30
      },
      {
        "id": 50,
        "text": "Wrong",
        "image": null,
        "is_correct": false,
        "question": 30
      }
    ],
    "question_type": "MCQ",
    "comment": null,
    "created": "2026-05-10T06:42:36.215061Z"
  }
]
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Each `questions[i]` item must include valid question fields.
- Optional `exam_id` must reference an existing exam if used.
- Nested answers are validated per answer.

### 48. 17 Count Questions
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/questions/count/?course={{course_math_id}}&question_type=MCQ`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 5,
  "active_count": 5,
  "mcq_count": 5,
  "essay_count": 0,
  "easy_count": 4,
  "medium_count": 1,
  "hard_count": 0
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- Filters must reference existing enum values/IDs when supplied.

### 49. 18 Add Similar Questions
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/questions/{{q_course_id}}/similars/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "question_ids": [
    "{{q_similar_id}}"
  ]
}
```
**Tested Response:** `200 OK`

```json
{
  "message": "Similar questions processed successfully",
  "main_question_id": 24,
  "added_count": 1,
  "total_similar_questions": 1
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `question_ids` must be a non-empty list of active MCQ question IDs.
- The main question must exist and be active.
- The main question ID is ignored if included in its own similar list.

### 50. 19 List Answers For Course Question
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/answers/?question={{q_course_id}}`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 39,
      "text": "4",
      "image": null,
      "is_correct": true,
      "question": 24
    },
    {
      "id": 40,
      "text": "10",
      "image": null,
      "is_correct": false,
      "question": 24
    }
  ]
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `question` must reference an existing question on create.
- `text` is required.
- `is_correct` must be boolean when supplied.
- Answer image must be a valid image when uploaded.

### 51. 20 Create Extra Answer
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/answers/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `form-data`
**Body Example:**

| Key | Type | Example | Required | Notes |
|---|---|---|---|---|
| `question` | `text` | `{{q_similar_id}}` | Yes/conditional |  |
| `text` | `text` | `Extra distractor` | Yes/conditional |  |
| `is_correct` | `text` | `false` | Yes/conditional |  |
| `image` | `file` | `` | No | Optional file field. Enable and select a local file if you want to test uploads. |
**Tested Response:** `201 Created`

```json
{
  "id": 51,
  "text": "Extra distractor",
  "image": null,
  "is_correct": false,
  "question": 27
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `question` must reference an existing question on create.
- `text` is required.
- `is_correct` must be boolean when supplied.
- Answer image must be a valid image when uploaded.

### 52. 21 Get Answer Detail
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/answers/{{answer_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "id": 39,
  "text": "4",
  "image": null,
  "is_correct": true,
  "question": 24
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `question` must reference an existing question on create.
- `text` is required.
- `is_correct` must be boolean when supplied.
- Answer image must be a valid image when uploaded.

### 53. 22 Update Extra Answer
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `PATCH`
**URL:** `{{base_url}}/dashboard/answers/{{answer_delete_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `form-data`
**Body Example:**

| Key | Type | Example | Required | Notes |
|---|---|---|---|---|
| `text` | `text` | `Updated extra distractor` | Yes/conditional |  |
| `image` | `file` | `` | No | Optional file field. Enable and select a local file if you want to test uploads. |
**Tested Response:** `200 OK`

```json
{
  "id": 51,
  "text": "Updated extra distractor",
  "image": null,
  "is_correct": false,
  "question": 27
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `question` must reference an existing question on create.
- `text` is required.
- `is_correct` must be boolean when supplied.
- Answer image must be a valid image when uploaded.

### 54. 23 Delete Extra Answer
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `DELETE`
**URL:** `{{base_url}}/dashboard/answers/{{answer_delete_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `204 No Content`

_Empty response body._
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `question` must reference an existing question on create.
- `text` is required.
- `is_correct` must be boolean when supplied.
- Answer image must be a valid image when uploaded.

### 55. 24 Create Manual Course Exam
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/exams/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "title": "EST Math Diagnostic {{scenario_suffix}}",
  "description": "Course diagnostic exam for EST Math.",
  "related_to": "COURSE",
  "course": "{{course_math_id}}",
  "number_of_questions": 3,
  "time_limit": 45,
  "passing_percent": 60,
  "number_of_allowed_trials": 3,
  "start": "{{exam_start_at}}",
  "end": "{{exam_end_at}}",
  "show_answers_after_finish": true,
  "allow_show_results_at": "{{allow_show_results_at}}",
  "is_active": true
}
```
**Tested Response:** `201 Created`

```json
{
  "id": 22,
  "title": "EST Math Diagnostic 95350672",
  "description": "Course diagnostic exam for EST Math.",
  "related_to": "COURSE",
  "course": 16,
  "related_course": 16,
  "related_course_name": "EST Math 95350672",
  "unit": null,
  "related_unit": null,
  "related_unit_name": null,
  "type": "MANUAL",
  "number_of_questions": 3,
  "time_limit": 45,
  "score": 0.0,
  "passing_percent": 60,
  "number_of_allowed_trials": 3,
  "easy_questions_count": 0,
  "medium_questions_count": 0,
  "hard_questions_count": 0,
  "show_answers_after_finish": true,
  "order": 1,
  "is_active": true,
  "start": "2026-05-10T05:42:36.815000Z",
  "end": "2026-05-11T06:42:36.815000Z",
  "allow_show_results_at": "2026-05-10T06:41:36.815000Z",
  "allow_show_answers_at": null,
  "created": "2026-05-10T06:42:36.841093Z",
  "status": "active",
  "calculated_score": 0,
  "calculated_number_of_questions": 0,
  "is_depends": false,
  "ponus_option": null,
  "ponus": 0,
  "show_questions_in_random": true
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `related_to` must be `COURSE` or `UNIT`.
- Course is required for course exams; unit is required for unit exams.
- A course exam cannot also target a unit.
- Random exam difficulty counts cannot exceed `number_of_questions` and must have enough matching questions.
- `start` and `end` must be valid datetimes.

### 56. 25 Create Empty Exam For Bank/Manual Endpoint Tests
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/exams/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "title": "Question Bank Target {{scenario_suffix}}",
  "related_to": "COURSE",
  "course": "{{course_math_id}}",
  "number_of_questions": 1,
  "time_limit": 20,
  "passing_percent": 50,
  "number_of_allowed_trials": 1,
  "start": "{{exam_start_at}}",
  "end": "{{exam_end_at}}",
  "is_active": true
}
```
**Tested Response:** `201 Created`

```json
{
  "id": 23,
  "title": "Question Bank Target 95350672",
  "description": null,
  "related_to": "COURSE",
  "course": 16,
  "related_course": 16,
  "related_course_name": "EST Math 95350672",
  "unit": null,
  "related_unit": null,
  "related_unit_name": null,
  "type": "MANUAL",
  "number_of_questions": 1,
  "time_limit": 20,
  "score": 0.0,
  "passing_percent": 50,
  "number_of_allowed_trials": 1,
  "easy_questions_count": 0,
  "medium_questions_count": 0,
  "hard_questions_count": 0,
  "show_answers_after_finish": false,
  "order": 2,
  "is_active": true,
  "start": "2026-05-10T05:42:36.919000Z",
  "end": "2026-05-11T06:42:36.919000Z",
  "allow_show_results_at": "2026-05-10T06:42:36.938739Z",
  "allow_show_answers_at": null,
  "created": "2026-05-10T06:42:36.940069Z",
  "status": "active",
  "calculated_score": 0,
  "calculated_number_of_questions": 0,
  "is_depends": false,
  "ponus_option": null,
  "ponus": 0,
  "show_questions_in_random": true
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `related_to` must be `COURSE` or `UNIT`.
- Course is required for course exams; unit is required for unit exams.
- A course exam cannot also target a unit.
- Random exam difficulty counts cannot exceed `number_of_questions` and must have enough matching questions.
- `start` and `end` must be valid datetimes.

### 57. 26 Create Random Exam
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/exams/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "title": "Random Practice {{scenario_suffix}}",
  "related_to": "COURSE",
  "course": "{{course_math_id}}",
  "type": "RANDOM",
  "number_of_questions": 2,
  "time_limit": 20,
  "passing_percent": 50,
  "number_of_allowed_trials": 1,
  "start": "{{exam_start_at}}",
  "end": "{{exam_end_at}}",
  "is_active": true
}
```
**Tested Response:** `201 Created`

```json
{
  "id": 24,
  "title": "Random Practice 95350672",
  "description": null,
  "related_to": "COURSE",
  "course": 16,
  "related_course": 16,
  "related_course_name": "EST Math 95350672",
  "unit": null,
  "related_unit": null,
  "related_unit_name": null,
  "type": "RANDOM",
  "number_of_questions": 2,
  "time_limit": 20,
  "score": 0.0,
  "passing_percent": 50,
  "number_of_allowed_trials": 1,
  "easy_questions_count": 0,
  "medium_questions_count": 0,
  "hard_questions_count": 0,
  "show_answers_after_finish": false,
  "order": 3,
  "is_active": true,
  "start": "2026-05-10T05:42:37.013000Z",
  "end": "2026-05-11T06:42:37.013000Z",
  "allow_show_results_at": "2026-05-10T06:42:37.029271Z",
  "allow_show_answers_at": null,
  "created": "2026-05-10T06:42:37.030480Z",
  "status": "active",
  "calculated_score": "not_calculatable",
  "calculated_number_of_questions": "not_calculatable",
  "is_depends": false,
  "ponus_option": null,
  "ponus": 0,
  "show_questions_in_random": true
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `related_to` must be `COURSE` or `UNIT`.
- Course is required for course exams; unit is required for unit exams.
- A course exam cannot also target a unit.
- Random exam difficulty counts cannot exceed `number_of_questions` and must have enough matching questions.
- `start` and `end` must be valid datetimes.

### 58. 27 Create Throwaway Exam
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/exams/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "title": "Delete Exam {{scenario_suffix}}",
  "related_to": "COURSE",
  "course": "{{course_math_id}}",
  "number_of_questions": 1,
  "time_limit": 10,
  "start": "{{exam_start_at}}",
  "end": "{{exam_end_at}}",
  "is_active": true
}
```
**Tested Response:** `201 Created`

```json
{
  "id": 25,
  "title": "Delete Exam 95350672",
  "description": null,
  "related_to": "COURSE",
  "course": 16,
  "related_course": 16,
  "related_course_name": "EST Math 95350672",
  "unit": null,
  "related_unit": null,
  "related_unit_name": null,
  "type": "MANUAL",
  "number_of_questions": 1,
  "time_limit": 10,
  "score": 0.0,
  "passing_percent": 50,
  "number_of_allowed_trials": 1,
  "easy_questions_count": 0,
  "medium_questions_count": 0,
  "hard_questions_count": 0,
  "show_answers_after_finish": false,
  "order": 4,
  "is_active": true,
  "start": "2026-05-10T05:42:37.098000Z",
  "end": "2026-05-11T06:42:37.098000Z",
  "allow_show_results_at": "2026-05-10T06:42:37.110320Z",
  "allow_show_answers_at": null,
  "created": "2026-05-10T06:42:37.111088Z",
  "status": "active",
  "calculated_score": 0,
  "calculated_number_of_questions": 0,
  "is_depends": false,
  "ponus_option": null,
  "ponus": 0,
  "show_questions_in_random": true
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `related_to` must be `COURSE` or `UNIT`.
- Course is required for course exams; unit is required for unit exams.
- A course exam cannot also target a unit.
- Random exam difficulty counts cannot exceed `number_of_questions` and must have enough matching questions.
- `start` and `end` must be valid datetimes.

### 59. 28 List Exams
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/exams/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 22,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 25,
      "title": "Delete Exam 95350672",
      "description": null,
      "related_to": "COURSE",
      "course": 16,
      "related_course": 16,
      "related_course_name": "EST Math 95350672",
      "unit": null,
      "related_unit": null,
      "related_unit_name": null,
      "type": "MANUAL",
      "number_of_questions": 1,
      "time_limit": 10,
      "score": 0.0,
      "passing_percent": 50,
      "number_of_allowed_trials": 1,
      "easy_questions_count": 0,
      "medium_questions_count": 0,
      "hard_questions_count": 0,
      "show_answers_after_finish": false,
      "order": 4,
      "is_active": true,
      "start": "2026-05-10T05:42:37.098000Z",
      "end": "2026-05-11T06:42:37.098000Z",
      "allow_show_results_at": "2026-05-10T06:42:37.110320Z",
      "allow_show_answers_at": null,
      "created": "2026-05-10T06:42:37.111088Z",
      "status": "active",
      "calculated_score": 0,
      "calculated_number_of_questions": 0,
      "is_depends": false,
      "ponus_option": null,
      "ponus": 0,
      "show_questions_in_random": true
    },
    {
      "id": 24,
      "title": "Random Practice 95350672",
      "description": null,
      "related_to": "COURSE",
      "course": 16,
      "related_course": 16,
      "related_course_name": "EST Math 95350672",
      "unit": null,
      "related_unit": null,
      "related_unit_name": null,
      "type": "RANDOM",
      "number_of_questions": 2,
      "time_limit": 20,
      "score": 0.0,
      "passing_percent": 50,
      "number_of_allowed_trials": 1,
      "easy_questions_count": 0,
      "medium_questions_count": 0,
      "hard_questions_count": 0,
      "show_answers_after_finish": false,
      "order": 3,
... truncated for documentation ...
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `related_to` must be `COURSE` or `UNIT`.
- Course is required for course exams; unit is required for unit exams.
- A course exam cannot also target a unit.
- Random exam difficulty counts cannot exceed `number_of_questions` and must have enough matching questions.
- `start` and `end` must be valid datetimes.

### 60. 29 Get Manual Exam Detail
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/exams/{{exam_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "id": 22,
  "title": "EST Math Diagnostic 95350672",
  "description": "Course diagnostic exam for EST Math.",
  "related_to": "COURSE",
  "course": 16,
  "related_course": 16,
  "related_course_name": "EST Math 95350672",
  "unit": null,
  "related_unit": null,
  "related_unit_name": null,
  "type": "MANUAL",
  "number_of_questions": 3,
  "time_limit": 45,
  "score": 0.0,
  "passing_percent": 60,
  "number_of_allowed_trials": 3,
  "easy_questions_count": 0,
  "medium_questions_count": 0,
  "hard_questions_count": 0,
  "show_answers_after_finish": true,
  "order": 1,
  "is_active": true,
  "start": "2026-05-10T05:42:36.815000Z",
  "end": "2026-05-11T06:42:36.815000Z",
  "allow_show_results_at": "2026-05-10T06:41:36.815000Z",
  "allow_show_answers_at": null,
  "created": "2026-05-10T06:42:36.841093Z",
  "status": "active",
  "calculated_score": 0,
  "calculated_number_of_questions": 0,
  "is_depends": false,
  "ponus_option": null,
  "ponus": 0,
  "show_questions_in_random": true
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `related_to` must be `COURSE` or `UNIT`.
- Course is required for course exams; unit is required for unit exams.
- A course exam cannot also target a unit.
- Random exam difficulty counts cannot exceed `number_of_questions` and must have enough matching questions.
- `start` and `end` must be valid datetimes.

### 61. 30 Update Manual Exam
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `PATCH`
**URL:** `{{base_url}}/dashboard/exams/{{exam_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "description": "Updated diagnostic exam."
}
```
**Tested Response:** `200 OK`

```json
{
  "id": 22,
  "title": "EST Math Diagnostic 95350672",
  "description": "Updated diagnostic exam.",
  "related_to": "COURSE",
  "course": 16,
  "related_course": 16,
  "related_course_name": "EST Math 95350672",
  "unit": null,
  "related_unit": null,
  "related_unit_name": null,
  "type": "MANUAL",
  "number_of_questions": 3,
  "time_limit": 45,
  "score": 0.0,
  "passing_percent": 60,
  "number_of_allowed_trials": 3,
  "easy_questions_count": 0,
  "medium_questions_count": 0,
  "hard_questions_count": 0,
  "show_answers_after_finish": true,
  "order": 1,
  "is_active": true,
  "start": "2026-05-10T05:42:36.815000Z",
  "end": "2026-05-11T06:42:36.815000Z",
  "allow_show_results_at": "2026-05-10T06:41:36.815000Z",
  "allow_show_answers_at": null,
  "created": "2026-05-10T06:42:36.841093Z",
  "status": "active",
  "calculated_score": 0,
  "calculated_number_of_questions": 0,
  "is_depends": false,
  "ponus_option": null,
  "ponus": 0,
  "show_questions_in_random": true
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `related_to` must be `COURSE` or `UNIT`.
- Course is required for course exams; unit is required for unit exams.
- A course exam cannot also target a unit.
- Random exam difficulty counts cannot exceed `number_of_questions` and must have enough matching questions.
- `start` and `end` must be valid datetimes.

### 62. 31 Delete Throwaway Exam
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `DELETE`
**URL:** `{{base_url}}/dashboard/exams/{{exam_delete_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `204 No Content`

_Empty response body._
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `related_to` must be `COURSE` or `UNIT`.
- Course is required for course exams; unit is required for unit exams.
- A course exam cannot also target a unit.
- Random exam difficulty counts cannot exceed `number_of_questions` and must have enough matching questions.
- `start` and `end` must be valid datetimes.

### 63. 32 Assign Questions To Exam
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/exams/{{exam_id}}/questions/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "question_ids": [
    "{{q_course_id}}",
    "{{q_unit_id}}",
    "{{q_essay_id}}"
  ]
}
```
**Tested Response:** `201 Created`

```json
[
  {
    "id": 19,
    "exam_question_id": 19,
    "exam": 22,
    "question": {
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
          "image": null,
          "is_correct": true,
          "question": 24
        },
        {
          "id": 40,
          "text": "10",
          "image": null,
          "is_correct": false,
          "question": 24
        }
      ],
      "question_type": "MCQ",
      "comment": null,
      "created": "2026-05-10T06:42:35.245138Z",
      "exam_question_id": 19
    },
    "question_details": {
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
          "image": null,
          "is_correct": true,
          "question": 24
        },
        {
          "id": 40,
          "text": "10",
          "image": null,
          "is_correct": false,
          "question": 24
        }
      ],
      "question_type": "MCQ",
      "comment": null,
      "created": "2026-05-10T06:42:35.245138Z"
    },
    "is_active": true,
    "order": 1,
    "created": "2026-05-10T06:42:37.533907Z"
  },
  {
    "id": 20,
    "exam_question_id": 20,
    "exam": 22,
    "question": {
      "id": 25,
      "text": "Which expression equals 2(x + 5)?",
      "explanation": null,
      "image": null,
      "points": 3,
      "difficulty": "MEDIUM",
... truncated for documentation ...
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `question_ids` must be a non-empty list of existing question IDs.
- Duplicate exam questions are skipped.

### 64. 33 List Exam Questions Current Shape
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/exams/{{exam_id}}/questions/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
[
  {
    "id": 19,
    "exam_question_id": 19,
    "exam": 22,
    "question": {
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
          "image": null,
          "is_correct": true,
          "question": 24
        },
        {
          "id": 40,
          "text": "10",
          "image": null,
          "is_correct": false,
          "question": 24
        }
      ],
      "question_type": "MCQ",
      "comment": null,
      "created": "2026-05-10T06:42:35.245138Z",
      "exam_question_id": 19
    },
    "question_details": {
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
          "image": null,
          "is_correct": true,
          "question": 24
        },
        {
          "id": 40,
          "text": "10",
          "image": null,
          "is_correct": false,
          "question": 24
        }
      ],
      "question_type": "MCQ",
      "comment": null,
      "created": "2026-05-10T06:42:35.245138Z"
    },
    "is_active": true,
    "order": 1,
    "created": "2026-05-10T06:42:37.533907Z"
  },
  {
    "id": 20,
    "exam_question_id": 20,
    "exam": 22,
    "question": {
      "id": 25,
      "text": "Which expression equals 2(x + 5)?",
      "explanation": null,
      "image": null,
      "points": 3,
      "difficulty": "MEDIUM",
... truncated for documentation ...
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `question_ids` must be a non-empty list of existing question IDs.
- Duplicate exam questions are skipped.

### 65. 34 List Exam Questions Old Shape
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/exams/{{exam_id}}/questions/list/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "exam_id": 22,
  "exam_title": "EST Math Diagnostic 95350672",
  "questions": [
    {
      "id": 19,
      "exam_question_id": 19,
      "exam": 22,
      "question": {
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
            "image": null,
            "is_correct": true,
            "question": 24
          },
          {
            "id": 40,
            "text": "10",
            "image": null,
            "is_correct": false,
            "question": 24
          }
        ],
        "question_type": "MCQ",
        "comment": null,
        "created": "2026-05-10T06:42:35.245138Z",
        "exam_question_id": 19
      },
      "question_details": {
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
            "image": null,
            "is_correct": true,
            "question": 24
          },
          {
            "id": 40,
            "text": "10",
            "image": null,
            "is_correct": false,
            "question": 24
          }
        ],
        "question_type": "MCQ",
        "comment": null,
        "created": "2026-05-10T06:42:35.245138Z"
      },
      "is_active": true,
      "order": 1,
      "created": "2026-05-10T06:42:37.533907Z"
    },
    {
      "id": 20,
... truncated for documentation ...
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.

### 66. 35 Remove Essay From Exam Current Endpoint
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `DELETE`
**URL:** `{{base_url}}/dashboard/exams/{{exam_id}}/questions/{{q_essay_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `204 No Content`

_Empty response body._
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.

### 67. 36 Reassign Essay To Exam
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/exams/{{exam_id}}/questions/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "question_ids": [
    "{{q_essay_id}}"
  ]
}
```
**Tested Response:** `201 Created`

```json
[
  {
    "id": 22,
    "exam_question_id": 22,
    "exam": 22,
    "question": {
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
      "question_type": "ESSAY",
      "comment": "Show clear reasoning.",
      "created": "2026-05-10T06:42:35.477255Z",
      "exam_question_id": 22
    },
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
      "question_type": "ESSAY",
      "comment": "Show clear reasoning.",
      "created": "2026-05-10T06:42:35.477255Z"
    },
    "is_active": true,
    "order": 3,
    "created": "2026-05-10T06:42:37.916591Z"
  }
]
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `question_ids` must be a non-empty list of existing question IDs.
- Duplicate exam questions are skipped.

### 68. 37 Add Bank Questions To Empty Exam
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/exams/{{empty_exam_id}}/questions/bank/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "questions_ids": [
    "{{q_course_id}}",
    "{{q_unit_id}}"
  ]
}
```
**Tested Response:** `201 Created`

```json
{
  "message": "Questions added to the exam successfully",
  "exam_id": 23,
  "added_questions": [
    24,
    25
  ],
  "skipped_questions": []
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `questions_ids` or `question_ids` must be a list.
- Every question ID must exist.

### 69. 38 Add Manual Question Inside Empty Exam
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/exams/{{empty_exam_id}}/questions/manual/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `form-data`
**Body Example:**

| Key | Type | Example | Required | Notes |
|---|---|---|---|---|
| `text` | `text` | `Manual endpoint question` | Yes/conditional |  |
| `points` | `text` | `2` | Yes/conditional |  |
| `difficulty` | `text` | `EASY` | Yes/conditional |  |
| `category` | `text` | `{{category_id}}` | Yes/conditional |  |
| `course` | `text` | `{{course_math_id}}` | Yes/conditional |  |
| `question_type` | `text` | `MCQ` | Yes/conditional |  |
| `answers[0][text]` | `text` | `A` | Yes/conditional |  |
| `answers[0][is_correct]` | `text` | `true` | Yes/conditional |  |
| `answers[1][text]` | `text` | `B` | Yes/conditional |  |
| `answers[1][is_correct]` | `text` | `false` | Yes/conditional |  |
| `image` | `file` | `` | No | Optional file field. Enable and select a local file if you want to test uploads. |
**Tested Response:** `201 Created`

```json
{
  "message": "Question successfully created and added to the exam",
  "question": {
    "id": 31,
    "text": "Manual endpoint question",
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
        "id": 52,
        "text": "A",
        "image": null,
        "is_correct": true,
        "question": 31
      },
      {
        "id": 53,
        "text": "B",
        "image": null,
        "is_correct": false,
        "question": 31
      }
    ],
    "question_type": "MCQ",
    "comment": null,
    "created": "2026-05-10T06:42:38.128882Z"
  }
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Manual question body follows the question creation validation rules.
- Created question is attached to the target exam.

### 70. 39 Remove Manual Question Old Endpoint
**Flow:** `02 Dashboard Exam Setup - Categories Questions Exams`
**Method:** `DELETE`
**URL:** `{{base_url}}/dashboard/exams/{{empty_exam_id}}/questions/{{q_manual_id}}/remove/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "success": "Question removed from exam"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Question must already be attached to the exam.

## 03 Dashboard Random Exams and Models

### 71. 01 Add Random Exam Bank Questions
**Flow:** `03 Dashboard Random Exams and Models`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/exams/{{random_exam_id}}/random-bank/add/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "question_ids": [
    "{{q_course_id}}",
    "{{q_unit_id}}",
    "{{q_similar_id}}"
  ]
}
```
**Tested Response:** `201 Created`

```json
{
  "message": "Questions successfully added to the random exam bank"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Exam must exist and must be type `RANDOM`.
- Question IDs must exist before being added.

### 72. 02 Get Random Exam Bank
**Flow:** `03 Dashboard Random Exams and Models`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/exams/{{random_exam_id}}/random-bank/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "exam": 24,
  "questions": [
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
          "image": null,
          "is_correct": true,
          "question": 24
        },
        {
          "id": 40,
          "text": "10",
          "image": null,
          "is_correct": false,
          "question": 24
        }
      ],
      "question_type": "MCQ",
      "comment": null,
      "created": "2026-05-10T06:42:35.245138Z"
    },
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
          "is_correct": true,
          "question": 25
        },
        {
          "id": 42,
          "text": "2x + 5",
          "image": null,
          "is_correct": false,
          "question": 25
        }
      ],
      "question_type": "MCQ",
      "comment": null,
      "created": "2026-05-10T06:42:35.355039Z"
    },
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
          "is_correct": true,
          "question": 27
... truncated for documentation ...
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Exam must exist and must be type `RANDOM`.
- Question IDs must exist before being added.

### 73. 03 Create Exam Model A
**Flow:** `03 Dashboard Random Exams and Models`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/exam-models/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "exam": "{{random_exam_id}}",
  "title": "Model A {{scenario_suffix}}",
  "is_active": true
}
```
**Tested Response:** `201 Created`

```json
{
  "id": 7,
  "title": "Model A 95350672",
  "created": "2026-05-10T06:42:38.488459Z",
  "is_active": true,
  "exam": 24
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Exam model must reference an existing exam on create.
- Model title is required.
- Question removal requires an existing model-question relation.

### 74. 04 Create Exam Model B For Delete
**Flow:** `03 Dashboard Random Exams and Models`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/exam-models/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "exam": "{{random_exam_id}}",
  "title": "Model B Delete {{scenario_suffix}}",
  "is_active": true
}
```
**Tested Response:** `201 Created`

```json
{
  "id": 8,
  "title": "Model B Delete 95350672",
  "created": "2026-05-10T06:42:38.572672Z",
  "is_active": true,
  "exam": 24
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Exam model must reference an existing exam on create.
- Model title is required.
- Question removal requires an existing model-question relation.

### 75. 05 List Exam Models
**Flow:** `03 Dashboard Random Exams and Models`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/exam-models/?exam={{random_exam_id}}`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 7,
      "title": "Model A 95350672",
      "created": "2026-05-10T06:42:38.488459Z",
      "is_active": true,
      "exam": 24
    },
    {
      "id": 8,
      "title": "Model B Delete 95350672",
      "created": "2026-05-10T06:42:38.572672Z",
      "is_active": true,
      "exam": 24
    }
  ]
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- Exam model must reference an existing exam on create.
- Model title is required.
- Question removal requires an existing model-question relation.

### 76. 06 Get Exam Model Detail
**Flow:** `03 Dashboard Random Exams and Models`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/exam-models/{{exam_model_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "id": 7,
  "title": "Model A 95350672",
  "created": "2026-05-10T06:42:38.488459Z",
  "is_active": true,
  "exam": 24
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Exam model must reference an existing exam on create.
- Model title is required.
- Question removal requires an existing model-question relation.

### 77. 07 Update Exam Model
**Flow:** `03 Dashboard Random Exams and Models`
**Method:** `PATCH`
**URL:** `{{base_url}}/dashboard/exam-models/{{exam_model_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "title": "Model A Updated {{scenario_suffix}}"
}
```
**Tested Response:** `200 OK`

```json
{
  "id": 7,
  "title": "Model A Updated 95350672",
  "created": "2026-05-10T06:42:38.488459Z",
  "is_active": true,
  "exam": 24
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Exam model must reference an existing exam on create.
- Model title is required.
- Question removal requires an existing model-question relation.

### 78. 08 Suggest Questions For Random Model
**Flow:** `03 Dashboard Random Exams and Models`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/exams/{{random_exam_id}}/suggest-model-questions/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "exam_id": 24,
  "exam_title": "Random Practice 95350672",
  "questions": [
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
          "image": null,
          "is_correct": true,
          "question": 24
        },
        {
          "id": 40,
          "text": "10",
          "image": null,
          "is_correct": false,
          "question": 24
        }
      ],
      "question_type": "MCQ",
      "comment": null,
      "created": "2026-05-10T06:42:35.245138Z"
    },
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
          "is_correct": true,
          "question": 25
        },
        {
          "id": 42,
          "text": "2x + 5",
          "image": null,
          "is_correct": false,
          "question": 25
        }
      ],
      "question_type": "MCQ",
      "comment": null,
      "created": "2026-05-10T06:42:35.355039Z"
    }
  ]
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Exam must be type `RANDOM`.
- Random bank must exist.
- Bank must contain enough active questions for the exam count/difficulty distribution.

### 79. 09 Add Questions To Model
**Flow:** `03 Dashboard Random Exams and Models`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/exams/{{random_exam_id}}/models/{{exam_model_id}}/questions/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "question_ids": [
    "{{q_course_id}}",
    "{{q_unit_id}}"
  ]
}
```
**Tested Response:** `201 Created`

```json
{
  "message": "Questions added to the exam model successfully",
  "model_id": 7,
  "added_questions": [
    24,
    25
  ],
  "skipped_questions": []
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `question_ids` must be a non-empty list of existing question IDs.
- Duplicate exam questions are skipped.
- Exam and model must exist and belong together.
- `question_ids` must be valid existing questions.
- Duplicate model questions are skipped.

### 80. 10 List Exam Model Questions
**Flow:** `03 Dashboard Random Exams and Models`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/exam-models/{{exam_model_id}}/questions/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "exam_model_id": 7,
  "exam_model_title": "Model A Updated 95350672",
  "questions": [
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
          "image": null,
          "is_correct": true,
          "question": 24
        },
        {
          "id": 40,
          "text": "10",
          "image": null,
          "is_correct": false,
          "question": 24
        }
      ],
      "question_type": "MCQ",
      "comment": null,
      "created": "2026-05-10T06:42:35.245138Z"
    },
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
          "is_correct": true,
          "question": 25
        },
        {
          "id": 42,
          "text": "2x + 5",
          "image": null,
          "is_correct": false,
          "question": 25
        }
      ],
      "question_type": "MCQ",
      "comment": null,
      "created": "2026-05-10T06:42:35.355039Z"
    }
  ]
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Exam model must reference an existing exam on create.
- Model title is required.
- Question removal requires an existing model-question relation.

### 81. 11 Remove Question From Model
**Flow:** `03 Dashboard Random Exams and Models`
**Method:** `DELETE`
**URL:** `{{base_url}}/dashboard/exam-models/{{exam_model_id}}/questions/{{q_unit_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "message": "Question successfully removed from the exam model"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Exam model must reference an existing exam on create.
- Model title is required.
- Question removal requires an existing model-question relation.

### 82. 12 Delete Throwaway Exam Model
**Flow:** `03 Dashboard Random Exams and Models`
**Method:** `DELETE`
**URL:** `{{base_url}}/dashboard/exam-models/{{exam_model_delete_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `204 No Content`

_Empty response body._
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Exam model must reference an existing exam on create.
- Model title is required.
- Question removal requires an existing model-question relation.

## 05 Student Plans Courses Subscription Payment

### 83. 09 Dashboard Confirm Plan Subscription
**Flow:** `05 Student Plans Courses Subscription Payment`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/plans/subscriptions/{{subscription_id}}/confirm/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

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
  "payment_status": "manual",
  "has_access_now": true,
  "easypay_invoice_uid": null,
  "easypay_invoice_sequence": null,
  "easypay_payment_url": null,
  "paid_at": "2026-05-10T06:42:40.703887Z",
  "created_at": "2026-05-10T06:42:40.251314Z"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Subscription must exist.
- Confirming payment marks it paid/manual and syncs course access rows.

### 84. 10 Subscription App Manual Confirm Endpoint
**Flow:** `05 Student Plans Courses Subscription Payment`
**Method:** `POST`
**URL:** `{{base_url}}/plans/subscriptions/{{subscription_id}}/manual-confirm/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

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
  "payment_status": "manual",
  "has_access_now": true,
  "easypay_invoice_uid": null,
  "easypay_invoice_sequence": null,
  "easypay_payment_url": null,
  "paid_at": "2026-05-10T06:42:40.703887Z",
  "created_at": "2026-05-10T06:42:40.251314Z"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Requires admin/staff even though route is under `/plans/`.
- Subscription must exist.

### 85. 11 List Dashboard Subscriptions
**Flow:** `05 Student Plans Courses Subscription Payment`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/plans/subscriptions/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 5,
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
    },
    {
      "id": 4,
      "plan": {
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
      "courses": [
        {
          "id": 7,
          "name": "E
... truncated for documentation ...
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- Subscription must exist.
- Confirming payment marks it paid/manual and syncs course access rows.

## 06 Student Course Exam Attempt

### 86. 08 Set Temp Exam Daily Limit
**Flow:** `06 Student Course Exam Attempt`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/temp-exam-allowed-times/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "number_of_allowedtempexams_per_day": 5
}
```
**Tested Response:** `200 OK`

```json
{
  "message": "Temp exam allowed times updated successfully",
  "number_of_allowedtempexams_per_day": 5
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `number_of_allowedtempexams_per_day` must be zero or greater.
- This updates the singleton temp-exam limit row.

## 07 Student Created Exams and Admin Question Bank

### 87. 01 Admin Question Bank Create Course Question
**Flow:** `07 Student Created Exams and Admin Question Bank`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/admin-question-bank/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "question": "{{q_course_id}}"
}
```
**Tested Response:** `201 Created`

```json
{
  "id": 2,
  "question_details": {
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
        "image": null,
        "is_correct": true,
        "question": 24
      },
      {
        "id": 40,
        "text": "10",
        "image": null,
        "is_correct": false,
        "question": 24
      }
    ],
    "question_type": "MCQ",
    "comment": null,
    "created": "2026-05-10T06:42:35.245138Z"
  },
  "question_text": "If x + 3 = 7, what is x?",
  "question_type": "MCQ",
  "question_points": 2,
  "created": "2026-05-10T06:42:42.288329Z"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Question IDs must exist and be active for bulk add.
- Single create requires `question` ID.
- Duplicate existing bank entries are reported/skipped where bulk is used.

### 88. 02 Admin Question Bank Bulk Create
**Flow:** `07 Student Created Exams and Admin Question Bank`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/admin-question-bank/bulk/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "questions": [
    "{{q_unit_id}}",
    "{{q_essay_id}}",
    "{{q_similar_id}}"
  ]
}
```
**Tested Response:** `201 Created`

```json
{
  "success": true,
  "summary": {
    "total_requested": 3,
    "successfully_added": 3,
    "already_existed": 0
  },
  "details": {
    "added_question_ids": [
      25,
      26,
      27
    ],
    "already_existed_ids": []
  }
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Question IDs must exist and be active for bulk add.
- Single create requires `question` ID.
- Duplicate existing bank entries are reported/skipped where bulk is used.

### 89. 03 Dashboard Admin Question Bank List
**Flow:** `07 Student Created Exams and Admin Question Bank`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/admin-question-bank/?question__course={{course_math_id}}`
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
            "is_correct": true,
            "question": 27
          },
          {
            "id": 44,
            "text": "3",
            "image": null,
            "is_correct": false,
            "question": 27
          }
        ],
        "question_type": "MCQ",
        "comment": "reviewed by Postman",
        "created": "2026-05-10T06:42:35.579462Z"
      },
      "question_text": "Which value satisfies x - 1 = 4?",
      "question_type": "MCQ",
      "question_points": 2,
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
        "question_type": "ESSAY",
        "comment": "Show clear reasoning.",
        "created": "2026-05-10T06:42:35.477255Z"
      },
      "question_text": "Explain how to solve a linear equation in one variable.",
      "question_type": "ESSAY",
      "question_points": 5,
      "created": "2026-05-10T06:42:42.368759Z"
    },
    {
      "id": 3
... truncated for documentation ...
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- Question IDs must exist and be active for bulk add.
- Single create requires `question` ID.
- Duplicate existing bank entries are reported/skipped where bulk is used.

### 90. 08 Delete One Admin Question Bank Entry
**Flow:** `07 Student Created Exams and Admin Question Bank`
**Method:** `DELETE`
**URL:** `{{base_url}}/dashboard/admin-question-bank/{{admin_bank_entry_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `204 No Content`

_Empty response body._
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Question IDs must exist and be active for bulk add.
- Single create requires `question` ID.
- Duplicate existing bank entries are reported/skipped where bulk is used.

## 08 Dashboard Result Trial Reporting

### 91. 01 List Essay Submissions
**Flow:** `08 Dashboard Result Trial Reporting`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/essay-submissions/?exam={{exam_id}}`
**Authentication:** Bearer token: `{{admin_access_token}}`
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
      "student": "Mariam EST Updated 95350672",
      "exam": "EST Math Diagnostic 95350672",
      "question": "Explain how to solve a linear equation in one variable.",
      "answer_text": "Move constants to one side, then divide by the coefficient.",
      "answer_file_url": null,
      "score": null,
      "is_scored": false,
      "created": "2026-05-10T06:42:41.506957Z",
      "result_trial": 8,
      "question_explanation": "Move constants to one side and divide by coefficient.",
      "question_comment": "Show clear reasoning.",
      "question_image": null
    }
  ]
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- Filter IDs must be valid when supplied.
- Only staff can list essay submissions.

### 92. 02 Score Essay Submission
**Flow:** `08 Dashboard Result Trial Reporting`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/essay-submissions/{{essay_submission_id}}/score/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "score": 4
}
```
**Tested Response:** `200 OK`

```json
{
  "message": "Essay question scored successfully",
  "submission": {
    "id": 2,
    "student": "Mariam EST Updated 95350672",
    "exam": "EST Math Diagnostic 95350672",
    "question": "Explain how to solve a linear equation in one variable.",
    "answer_text": "Move constants to one side, then divide by the coefficient.",
    "answer_file_url": null,
    "score": 4.0,
    "is_scored": true,
    "created": "2026-05-10T06:42:41.506957Z",
    "result_trial": 8,
    "question_explanation": "Move constants to one side and divide by coefficient.",
    "question_comment": "Show clear reasoning.",
    "question_image": null
  }
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Essay submission must exist.
- `score` must be numeric.
- Score must be between 0 and the question points.

### 93. 03 Dashboard Results List
**Flow:** `08 Dashboard Result Trial Reporting`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/results/?exam={{exam_id}}`
**Authentication:** Bearer token: `{{admin_access_token}}`
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
      "exam_score": 10.0,
      "student_score": 6.0,
      "trials": 1,
      "number_of_allowed_trials": 3,
      "correct_questions_count": 0,
      "incorrect_questions_count": 0,
      "insolved_questions_count": 0,
      "allowed_to_show_result": true,
      "student_id": 13,
      "student_name": "Mariam EST Updated 95350672",
      "student_phone": "01095350672",
      "parent_phone": "01111111111",
      "student_started_exam_at": "2026-05-10T06:42:41.368401Z",
      "student_submitted_exam_at": "2026-05-10T06:42:41.515491Z",
      "submit_type": "student_submit"
    }
  ]
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- Result/trial IDs must exist.
- Manual result-trial creation/update validates serializer field types.
- Reducing a result trial requires at least one trial.

### 94. 04 Dashboard Result Detail
**Flow:** `08 Dashboard Result Trial Reporting`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/results/{{result_id}}/detail/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "active_trial": 8,
  "trial_number": 1,
  "student_id": 13,
  "student_name": "Mariam EST Updated 95350672",
  "exam_id": 22,
  "exam_title": "EST Math Diagnostic 95350672",
  "exam_description": "Updated diagnostic exam.",
  "exam_score": 10.0,
  "student_score": 6.0,
  "is_succeeded": true,
  "student_trials": 1,
  "is_trials_finished": false,
  "number_of_essay": 1,
  "number_of_mcq": 2,
  "correct_mcq_count": 1,
  "incorrect_mcq_count": 1,
  "unsolved_mcq_count": 0,
  "correct_essay_count": 1,
  "incorrect_essay_count": 0,
  "unscored_essay_count": 0,
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
... truncated for documentation ...
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Result/trial IDs must exist.
- Manual result-trial creation/update validates serializer field types.
- Reducing a result trial requires at least one trial.

### 95. 05 Dashboard Result Trials
**Flow:** `08 Dashboard Result Trial Reporting`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/results/{{result_id}}/trials/`
**Authentication:** Bearer token: `{{admin_access_token}}`
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
      "id": 8,
      "result": 5,
      "trial": 1,
      "score": 6.0,
      "exam_score": 10.0,
      "exam_model": null,
      "submit_type": "student_submit",
      "student_started_exam_at": "2026-05-10T06:42:41.368401Z",
      "student_submitted_exam_at": "2026-05-10T06:42:41.515491Z"
    }
  ]
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Result/trial IDs must exist.
- Manual result-trial creation/update validates serializer field types.
- Reducing a result trial requires at least one trial.

### 96. 06 Dashboard Result Trial Detail
**Flow:** `08 Dashboard Result Trial Reporting`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/results/{{result_id}}/trials/{{result_trial_id}}/detail/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "active_trial": 8,
  "trial_number": 1,
  "student_id": 13,
  "student_name": "Mariam EST Updated 95350672",
  "exam_id": 22,
  "exam_title": "EST Math Diagnostic 95350672",
  "exam_description": "Updated diagnostic exam.",
  "exam_score": 10.0,
  "student_score": 6.0,
  "is_succeeded": true,
  "student_trials": 1,
  "is_trials_finished": false,
  "number_of_essay": 1,
  "number_of_mcq": 2,
  "correct_mcq_count": 1,
  "incorrect_mcq_count": 1,
  "unsolved_mcq_count": 0,
  "correct_essay_count": 1,
  "incorrect_essay_count": 0,
  "unscored_essay_count": 0,
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
... truncated for documentation ...
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Result/trial IDs must exist.
- Manual result-trial creation/update validates serializer field types.
- Reducing a result trial requires at least one trial.

### 97. 07 List All Trials
**Flow:** `08 Dashboard Result Trial Reporting`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/trials/?result__exam={{exam_id}}`
**Authentication:** Bearer token: `{{admin_access_token}}`
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
      "active_trial": 8,
      "trial_number": 1,
      "student_id": 13,
      "student_name": "Mariam EST Updated 95350672",
      "exam_id": 22,
      "exam_title": "EST Math Diagnostic 95350672",
      "exam_description": "Updated diagnostic exam.",
      "exam_score": 10.0,
      "student_score": 6.0,
      "is_succeeded": true,
      "student_trials": 1,
      "is_trials_finished": false,
      "number_of_essay": 1,
      "number_of_mcq": 2,
      "correct_mcq_count": 1,
      "incorrect_mcq_count": 1,
      "unsolved_mcq_count": 0,
      "correct_essay_count": 1,
      "incorrect_essay_count": 0,
      "unscored_essay_count": 0,
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
          "question_category": "EST Alge
... truncated for documentation ...
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- Result/trial IDs must exist.
- Manual result-trial creation/update validates serializer field types.
- Reducing a result trial requires at least one trial.

### 98. 08 Result Trial Expanded Detail
**Flow:** `08 Dashboard Result Trial Reporting`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/result-trials/{{result_trial_id}}/detail/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "active_trial": 8,
  "trial_number": 1,
  "student_id": 13,
  "student_name": "Mariam EST Updated 95350672",
  "exam_id": 22,
  "exam_title": "EST Math Diagnostic 95350672",
  "exam_description": "Updated diagnostic exam.",
  "exam_score": 10.0,
  "student_score": 6.0,
  "is_succeeded": true,
  "student_trials": 1,
  "is_trials_finished": false,
  "number_of_essay": 1,
  "number_of_mcq": 2,
  "correct_mcq_count": 1,
  "incorrect_mcq_count": 1,
  "unsolved_mcq_count": 0,
  "correct_essay_count": 1,
  "incorrect_essay_count": 0,
  "unscored_essay_count": 0,
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
... truncated for documentation ...
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Result/trial IDs must exist.
- Manual result-trial creation/update validates serializer field types.
- Reducing a result trial requires at least one trial.

### 99. 09 Create Additional Result Trial
**Flow:** `08 Dashboard Result Trial Reporting`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/result-trials/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "result": "{{result_id}}",
  "trial": 2,
  "score": 1,
  "exam_score": 10,
  "student_started_exam_at": "{{exam_start_at}}",
  "student_submitted_exam_at": "{{exam_end_at}}",
  "submit_type": "offline"
}
```
**Tested Response:** `201 Created`

```json
{
  "id": 9,
  "result": 5,
  "trial": 2,
  "score": 1.0,
  "exam_score": 10.0,
  "exam_model": null,
  "submit_type": "offline",
  "student_started_exam_at": "2026-05-10T05:42:43.654000Z",
  "student_submitted_exam_at": "2026-05-11T06:42:43.654000Z"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Result/trial IDs must exist.
- Manual result-trial creation/update validates serializer field types.
- Reducing a result trial requires at least one trial.

### 100. 09A Retrieve Additional Result Trial
**Flow:** `08 Dashboard Result Trial Reporting`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/result-trials/{{created_result_trial_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "id": 9,
  "result": 5,
  "trial": 2,
  "score": 1.0,
  "exam_score": 10.0,
  "exam_model": null,
  "submit_type": "offline",
  "student_started_exam_at": "2026-05-10T05:42:43.654000Z",
  "student_submitted_exam_at": "2026-05-11T06:42:43.654000Z"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Result/trial IDs must exist.
- Manual result-trial creation/update validates serializer field types.
- Reducing a result trial requires at least one trial.

### 101. 10 Update Additional Result Trial
**Flow:** `08 Dashboard Result Trial Reporting`
**Method:** `PATCH`
**URL:** `{{base_url}}/dashboard/result-trials/{{created_result_trial_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "submit_type": "tab_closed"
}
```
**Tested Response:** `200 OK`

```json
{
  "id": 9,
  "result": 5,
  "trial": 2,
  "score": 1.0,
  "exam_score": 10.0,
  "exam_model": null,
  "submit_type": "tab_closed",
  "student_started_exam_at": "2026-05-10T05:42:43.654000Z",
  "student_submitted_exam_at": "2026-05-11T06:42:43.654000Z"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Result/trial IDs must exist.
- Manual result-trial creation/update validates serializer field types.
- Reducing a result trial requires at least one trial.

### 102. 11 Delete Additional Result Trial
**Flow:** `08 Dashboard Result Trial Reporting`
**Method:** `DELETE`
**URL:** `{{base_url}}/dashboard/result-trials/{{created_result_trial_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `204 No Content`

_Empty response body._
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Result/trial IDs must exist.
- Manual result-trial creation/update validates serializer field types.
- Reducing a result trial requires at least one trial.

### 103. 12 Students Took Exam
**Flow:** `08 Dashboard Result Trial Reporting`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/exams/{{exam_id}}/students/took/`
**Authentication:** Bearer token: `{{admin_access_token}}`
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
      "id": 13,
      "student_user__username": "01095350672",
      "student_name": "Mariam EST Updated 95350672",
      "student_parent_phone": "01111111111",
      "student_code": null,
      "exam_id": 22,
      "exam_title": "EST Math Diagnostic 95350672",
      "examscore": 10.0,
      "student_score": 6.0,
      "trial": 1,
      "is_trials_finished": false,
      "issucceeded": true,
      "trials": [
        {
          "id": 8,
          "result": 5,
          "trial": 1,
          "score": 6.0,
          "exam_score": 10.0,
          "exam_model": null,
          "submit_type": "student_submit",
          "student_started_exam_at": "2026-05-10T06:42:41.368401Z",
          "student_submitted_exam_at": "2026-05-10T06:42:41.515491Z"
        }
      ]
    }
  ]
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Exam/student must exist.
- Student report endpoints use `Student.id`, not `User.id`.
- Search filters are optional.

### 104. 13 Students Did Not Take Exam
**Flow:** `08 Dashboard Result Trial Reporting`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/exams/{{exam_id}}/students/not-took/`
**Authentication:** Bearer token: `{{admin_access_token}}`
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
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Exam/student must exist.
- Student report endpoints use `Student.id`, not `User.id`.
- Search filters are optional.

### 105. 14 Exams Taken By Student
**Flow:** `08 Dashboard Result Trial Reporting`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/students/{{student_profile_id}}/exams/taken/`
**Authentication:** Bearer token: `{{admin_access_token}}`
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
      "exam_description": "Updated diagnostic exam.",
      "course_title": "EST Math 95350672",
      "unit_title": null,
      "passing_percent": 60.0,
      "exam_time_limit": 45,
      "examscore": 10.0,
      "student_score": 6.0,
      "exam_number_of_allowed_trials": 3,
      "trial": 1,
      "is_trials_finished": false,
      "issucceeded": true,
      "trials": [
        {
          "id": 8,
          "result": 5,
          "trial": 1,
          "score": 6.0,
          "exam_score": 10.0,
          "exam_model": null,
          "submit_type": "student_submit",
          "student_started_exam_at": "2026-05-10T06:42:41.368401Z",
          "student_submitted_exam_at": "2026-05-10T06:42:41.515491Z"
        }
      ]
    }
  ]
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Exam/student must exist.
- Student report endpoints use `Student.id`, not `User.id`.
- Search filters are optional.

### 106. 15 Exams Not Taken By Student
**Flow:** `08 Dashboard Result Trial Reporting`
**Method:** `GET`
**URL:** `{{base_url}}/dashboard/students/{{student_profile_id}}/exams/not-taken/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 23,
      "title": "Question Bank Target 95350672",
      "description": null,
      "related_to": "COURSE",
      "course": 16,
      "related_course": 16,
      "related_course_name": "EST Math 95350672",
      "unit": null,
      "related_unit": null,
      "related_unit_name": null,
      "type": "MANUAL",
      "number_of_questions": 2,
      "time_limit": 20,
      "score": 5.0,
      "passing_percent": 50,
      "number_of_allowed_trials": 1,
      "easy_questions_count": 0,
      "medium_questions_count": 0,
      "hard_questions_count": 0,
      "show_answers_after_finish": false,
      "order": 2,
      "is_active": true,
      "start": "2026-05-10T05:42:36.919000Z",
      "end": "2026-05-11T06:42:36.919000Z",
      "allow_show_results_at": "2026-05-10T06:42:36.938739Z",
      "allow_show_answers_at": null,
      "created": "2026-05-10T06:42:36.940069Z",
      "status": "active",
      "calculated_score": 5,
      "calculated_number_of_questions": 2,
      "is_depends": false,
      "ponus_option": null,
      "ponus": 0,
      "show_questions_in_random": true
    },
    {
      "id": 24,
      "title": "Random Practice 95350672",
      "description": null,
      "related_to": "COURSE",
      "course": 16,
      "related_course": 16,
      "related_course_name": "EST Math 95350672",
      "unit": null,
      "related_unit": null,
      "related_unit_name": null,
      "type": "RANDOM",
      "number_of_questions": 2,
      "time_limit": 20,
      "score": 0.0,
      "passing_percent": 50,
      "number_of_allowed_trials": 1,
      "easy_questions_count": 0,
      "medium_questions_count": 0,
      "hard_questions_count": 0,
      "show_answers_after_finish": false,
      "orde
... truncated for documentation ...
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Exam/student must exist.
- Student report endpoints use `Student.id`, not `User.id`.
- Search filters are optional.

### 107. 16 Copy Exam
**Flow:** `08 Dashboard Result Trial Reporting`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/exams/{{exam_id}}/copy/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "related_to": "COURSE",
  "course": "{{course_math_id}}"
}
```
**Tested Response:** `201 Created`

```json
{
  "id": 26,
  "message": "Exam copied successfully."
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `related_to` is required.
- Course is required for course copies; unit is required for unit copies.

### 108. 17 Reorder Exam Questions
**Flow:** `08 Dashboard Result Trial Reporting`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/exam-questions/reorder/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
[
  {
    "exam_question": "{{exam_question_1_id}}",
    "new_order": 2
  },
  {
    "exam_question": "{{exam_question_2_id}}",
    "new_order": 1
  }
]
```
**Tested Response:** `200 OK`

```json
{
  "detail": "ExamQuestions reordered successfully."
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Body must be a list.
- `exam_question` must reference an existing `ExamQuestion` row.
- `new_order` must be a positive integer.

### 109. 18 Reduce Result Trial
**Flow:** `08 Dashboard Result Trial Reporting`
**Method:** `POST`
**URL:** `{{base_url}}/dashboard/results/{{result_id}}/reduce-trial/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "message": "Trial reduced successfully. Result deleted as trial count reached zero."
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Result/trial IDs must exist.
- Manual result-trial creation/update validates serializer field types.
- Reducing a result trial requires at least one trial.

### 110. 19 Delete First Trial For Empty Exam
**Flow:** `08 Dashboard Result Trial Reporting`
**Method:** `DELETE`
**URL:** `{{base_url}}/dashboard/exams/{{empty_exam_id}}/trials/delete-first/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `404 Not Found`

```json
{
  "message": "No results found for this exam"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.

## 09 Dashboard Devices Ban Security

### 111. 01 Student Devices List
**Flow:** `09 Dashboard Devices Ban Security`
**Method:** `GET`
**URL:** `{{base_url}}/accounts/dashboard/students/devices/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 9,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 19,
      "username": "01195350672",
      "name": "Managed Student Updated 95350672",
      "max_allowed_devices": 2,
      "active_devices_count": 0,
      "is_banned": false,
      "banned_at": null,
      "ban_reason": null,
      "devices": []
    },
    {
      "id": 18,
      "username": "01095350672",
      "name": "Mariam EST Updated 95350672",
      "max_allowed_devices": 2,
      "active_devices_count": 1,
      "is_banned": false,
      "banned_at": null,
      "ban_reason": null,
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
    },
    {
      "id": 16,
      "username": "01295211654",
      "name": "OTP Student 95211654",
      "max_allowed_devices": 2,
      "active_devices_count": 1,
      "is_banned": false,
      "banned_at": null,
      "ban_reason": null,
      "devices": [
        {
          "id": 14,
          "device_id": "otp-device-95211654",
          "device_name": "OTP Postman Device",
          "ip_address": "127.0.0.1",
          "user_agent": "PostmanRuntime/7.39.1",
          "logged_in_at": "2026-05-10T06:40:32.381880Z",
          "last_used_at": "2026-05-10T06:40:32.381901Z",
          "is_active": true,
          "is_banned": false,
          "banned_at": null,
          "ban_reason": null
        }
      ]
    },
    {
... truncated for documentation ...
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- Student and device IDs must exist and belong together.
- Device remove/ban/unban only affects that student device.

### 112. 02 Main Student Devices Detail
**Flow:** `09 Dashboard Devices Ban Security`
**Method:** `GET`
**URL:** `{{base_url}}/accounts/dashboard/students/{{student_user_id}}/devices/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "id": 18,
  "username": "01095350672",
  "name": "Mariam EST Updated 95350672",
  "max_allowed_devices": 2,
  "active_devices_count": 1,
  "is_banned": false,
  "banned_at": null,
  "ban_reason": null,
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
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Student and device IDs must exist and belong together.
- Device remove/ban/unban only affects that student device.

### 113. 03 Update Main Student Max Devices
**Flow:** `09 Dashboard Devices Ban Security`
**Method:** `PATCH`
**URL:** `{{base_url}}/accounts/dashboard/students/{{student_user_id}}/max-devices/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "max_allowed_devices": 3
}
```
**Tested Response:** `200 OK`

```json
{
  "message": "تم تحديث الحد الأقصى للأجهزة إلى 3",
  "max_allowed_devices": 3,
  "active_devices_count": 1
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `max_allowed_devices` must be an integer accepted by the endpoint.
- Student must exist.

### 114. 04 Ban Main Student Device
**Flow:** `09 Dashboard Devices Ban Security`
**Method:** `POST`
**URL:** `{{base_url}}/accounts/dashboard/students/{{student_user_id}}/devices/{{student_device_id}}/ban/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "reason": "Postman device ban check"
}
```
**Tested Response:** `200 OK`

```json
{
  "message": "تم حظر الجهاز \"Postman Student Device\" بنجاح",
  "banned_at": "2026-05-10T06:42:44.986239Z"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Student and device IDs must exist and belong together.
- Device remove/ban/unban only affects that student device.

### 115. 05 Unban Main Student Device
**Flow:** `09 Dashboard Devices Ban Security`
**Method:** `POST`
**URL:** `{{base_url}}/accounts/dashboard/students/{{student_user_id}}/devices/{{student_device_id}}/unban/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "message": "تم إلغاء حظر الجهاز \"Postman Student Device\" بنجاح"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Student and device IDs must exist and belong together.
- Device remove/ban/unban only affects that student device.

### 116. 06 Remove Main Student Device
**Flow:** `09 Dashboard Devices Ban Security`
**Method:** `DELETE`
**URL:** `{{base_url}}/accounts/dashboard/students/{{student_user_id}}/devices/{{student_device_id}}/remove/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "message": "تم حذف الجهاز \"Postman Student Device\"",
  "active_devices_count": 0
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Student and device IDs must exist and belong together.
- Device remove/ban/unban only affects that student device.

### 117. 07 Student Re-Sign In After Device Removal
**Flow:** `09 Dashboard Devices Ban Security`
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
  "device_id": "postman-device-2-{{scenario_suffix}}",
  "device_name": "Postman Student Device 2"
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

### 118. 08 Remove All Main Student Devices
**Flow:** `09 Dashboard Devices Ban Security`
**Method:** `POST`
**URL:** `{{base_url}}/accounts/dashboard/students/{{student_user_id}}/devices/remove-all/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "message": "تم حذف 1 جهاز. تحذير: ميزة إدارة الرموز غير مفعلة",
  "active_devices_count": 0
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Student and device IDs must exist and belong together.
- Device remove/ban/unban only affects that student device.

### 119. 09 Student Re-Sign In After Remove All Devices
**Flow:** `09 Dashboard Devices Ban Security`
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
  "device_id": "postman-device-3-{{scenario_suffix}}",
  "device_name": "Postman Student Device 3"
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

### 120. 10 Ban Main Student
**Flow:** `09 Dashboard Devices Ban Security`
**Method:** `POST`
**URL:** `{{base_url}}/accounts/dashboard/students/{{student_user_id}}/ban/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "reason": "Postman account ban check"
}
```
**Tested Response:** `200 OK`

```json
{
  "message": "تم حظر الطالب \"Mariam EST Updated 95350672\" بنجاح",
  "banned_at": "2026-05-10T06:42:46.336018Z"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Student must exist.
- Ban/unban updates user ban fields.

### 121. 11 Sign In While Banned Expect 403
**Flow:** `09 Dashboard Devices Ban Security`
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
  "device_id": "postman-banned-{{scenario_suffix}}",
  "device_name": "Banned Device"
}
```
**Tested Response:** `403 Forbidden`

```json
{
  "error": "لقد تم حظر هذا الحساب"
}
```
**Validations And Error Cases:**
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `username` and `password` are required.
- Student account must not be banned.
- Failed attempts are tracked and may create a `SecurityBlock`.
- Device token/session is created or refreshed; device limits may remove old devices.

### 122. 12 Unban Main Student
**Flow:** `09 Dashboard Devices Ban Security`
**Method:** `POST`
**URL:** `{{base_url}}/accounts/dashboard/students/{{student_user_id}}/unban/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "message": "تم إلغاء حظر الطالب \"Mariam EST Updated 95350672\" بنجاح"
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Student must exist.
- Ban/unban updates user ban fields.

### 123. 13A Failed Login 1 For Security Block
**Flow:** `09 Dashboard Devices Ban Security`
**Description:** Intentional failed login to create authentication attempts/security block for dashboard security endpoints.
**Method:** `POST`
**URL:** `{{base_url}}/accounts/signin/`
**Authentication:** No bearer token required
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "username": "{{student_phone}}",
  "password": "WrongPass123",
  "device_id": "security-fail-1-{{scenario_suffix}}",
  "device_name": "Postman Failed Login Device"
}
```
**Tested Response:** `400 Bad Request`

```json
{
  "error": "بيانات الدخول غير صحيحة. لديك عدد (2) محاولات متبقية",
  "remaining_attempts": 2,
  "warning": "بيانات الدخول غير صحيحة. لديك عدد (2) محاولات متبقية"
}
```
**Validations And Error Cases:**
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `username` and `password` are required.
- Student account must not be banned.
- Failed attempts are tracked and may create a `SecurityBlock`.
- Device token/session is created or refreshed; device limits may remove old devices.

### 124. 13A Failed Login 2 For Security Block
**Flow:** `09 Dashboard Devices Ban Security`
**Description:** Intentional failed login to create authentication attempts/security block for dashboard security endpoints.
**Method:** `POST`
**URL:** `{{base_url}}/accounts/signin/`
**Authentication:** No bearer token required
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "username": "{{student_phone}}",
  "password": "WrongPass123",
  "device_id": "security-fail-2-{{scenario_suffix}}",
  "device_name": "Postman Failed Login Device"
}
```
**Tested Response:** `400 Bad Request`

```json
{
  "error": "بيانات الدخول غير صحيحة. لديك عدد (1) محاولات متبقية",
  "remaining_attempts": 1,
  "warning": "بيانات الدخول غير صحيحة. لديك عدد (1) محاولات متبقية"
}
```
**Validations And Error Cases:**
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `username` and `password` are required.
- Student account must not be banned.
- Failed attempts are tracked and may create a `SecurityBlock`.
- Device token/session is created or refreshed; device limits may remove old devices.

### 125. 13A Failed Login 3 Creates Security Block
**Flow:** `09 Dashboard Devices Ban Security`
**Description:** Intentional failed login to create authentication attempts/security block for dashboard security endpoints.
**Method:** `POST`
**URL:** `{{base_url}}/accounts/signin/`
**Authentication:** No bearer token required
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "username": "{{student_phone}}",
  "password": "WrongPass123",
  "device_id": "security-fail-3-{{scenario_suffix}}",
  "device_name": "Postman Failed Login Device"
}
```
**Tested Response:** `403 Forbidden`

```json
{
  "error": "تم حظر محاولات تسجيل الدخول لهذا الرقم مؤقتاً بسبب تجاوز عدد المحاولات المسموحة. سيتم رفع الحظر تلقائياً بعد 14 دقيقة. إذا لم تكن أنت من قام بهذه المحاولات، يرجى التواصل مع الدعم الفني فوراً.",
  "error_code": "account_blocked",
  "blocked_until": "2026-05-10T06:57:48.293569Z",
  "remaining_seconds": 899,
  "remaining_time": "14 دقيقة",
  "block_level": 1
}
```
**Validations And Error Cases:**
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `username` and `password` are required.
- Student account must not be banned.
- Failed attempts are tracked and may create a `SecurityBlock`.
- Device token/session is created or refreshed; device limits may remove old devices.

### 126. 13 Security Blocks List
**Flow:** `09 Dashboard Devices Ban Security`
**Method:** `GET`
**URL:** `{{base_url}}/accounts/dashboard/security/blocks/?search={{student_phone}}`
**Authentication:** Bearer token: `{{admin_access_token}}`
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
      "id": 8,
      "phone_number": "01095350672",
      "block_type": "login",
      "block_type_display": "Failed Login Attempts",
      "blocked_at": "2026-05-10T06:42:48.294657Z",
      "blocked_until": "2026-05-10T06:57:48.293569Z",
      "block_level": 1,
      "consecutive_blocks": 1,
      "is_active": true,
      "is_expired": false,
      "remaining_seconds": 899,
      "remaining_formatted": "14 دقيقة",
      "manually_unblocked": false,
      "unblocked_by": null,
      "unblocked_by_username": null,
      "unblocked_at": null,
      "unblock_reason": null,
      "failed_attempts": [
        {
          "timestamp": "2026-05-10T06:42:48.284002+00:00",
          "ip_address": "127.0.0.1",
          "device_id": "security-fail-3-95350672",
          "failure_reason": "بيانات الدخول غير صحيحة"
        },
        {
          "timestamp": "2026-05-10T06:42:47.809485+00:00",
          "ip_address": "127.0.0.1",
          "device_id": "security-fail-2-95350672",
          "failure_reason": "بيانات الدخول غير صحيحة"
        },
        {
          "timestamp": "2026-05-10T06:42:47.328270+00:00",
          "ip_address": "127.0.0.1",
          "device_id": "security-fail-1-95350672",
          "failure_reason": "بيانات الدخول غير صحيحة"
        }
      ],
      "ip_addresses": [
        "127.0.0.1"
      ],
      "user_agents": [
        "PostmanRuntime/7.39.1"
      ],
      "device_ids": [
        "security-fail-1-95350672",
        "security-fail-2-95350672",
        "security-fail-3-95350672"
      ]
    }
  ]
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- Security block/attempt IDs must exist where used.
- Manual unblock requires a phone number and optional reason.
- Deactivate/unblock operations require active admin permissions.

### 127. 14 Security Block Detail
**Flow:** `09 Dashboard Devices Ban Security`
**Method:** `GET`
**URL:** `{{base_url}}/accounts/dashboard/security/blocks/{{security_block_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "id": 8,
  "phone_number": "01095350672",
  "block_type": "login",
  "block_type_display": "Failed Login Attempts",
  "blocked_at": "2026-05-10T06:42:48.294657Z",
  "blocked_until": "2026-05-10T06:57:48.293569Z",
  "block_level": 1,
  "consecutive_blocks": 1,
  "is_active": true,
  "is_expired": false,
  "remaining_seconds": 899,
  "remaining_formatted": "14 دقيقة",
  "manually_unblocked": false,
  "unblocked_by": null,
  "unblocked_by_username": null,
  "unblocked_at": null,
  "unblock_reason": null,
  "failed_attempts": [
    {
      "timestamp": "2026-05-10T06:42:48.284002+00:00",
      "ip_address": "127.0.0.1",
      "device_id": "security-fail-3-95350672",
      "failure_reason": "بيانات الدخول غير صحيحة"
    },
    {
      "timestamp": "2026-05-10T06:42:47.809485+00:00",
      "ip_address": "127.0.0.1",
      "device_id": "security-fail-2-95350672",
      "failure_reason": "بيانات الدخول غير صحيحة"
    },
    {
      "timestamp": "2026-05-10T06:42:47.328270+00:00",
      "ip_address": "127.0.0.1",
      "device_id": "security-fail-1-95350672",
      "failure_reason": "بيانات الدخول غير صحيحة"
    }
  ],
  "ip_addresses": [
    "127.0.0.1"
  ],
  "user_agents": [
    "PostmanRuntime/7.39.1"
  ],
  "device_ids": [
    "security-fail-1-95350672",
    "security-fail-2-95350672",
    "security-fail-3-95350672"
  ],
  "recent_attempts": []
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Security block/attempt IDs must exist where used.
- Manual unblock requires a phone number and optional reason.
- Deactivate/unblock operations require active admin permissions.

### 128. 15 Deactivate Security Block
**Flow:** `09 Dashboard Devices Ban Security`
**Method:** `POST`
**URL:** `{{base_url}}/accounts/dashboard/security/blocks/{{security_block_id}}/deactivate/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "reason": "Postman cleanup"
}
```
**Tested Response:** `200 OK`

```json
{
  "success": true,
  "message": "تم إلغاء تفعيل الحظر الأمني بنجاح",
  "block": {
    "id": 8,
    "phone_number": "01095350672",
    "block_type": "login",
    "block_type_display": "Failed Login Attempts",
    "blocked_at": "2026-05-10T06:42:48.294657Z",
    "blocked_until": "2026-05-10T06:57:48.293569Z",
    "block_level": 1,
    "consecutive_blocks": 1,
    "is_active": false,
    "is_expired": false,
    "remaining_seconds": 0,
    "remaining_formatted": "انتهت مدة الحظر",
    "manually_unblocked": true,
    "unblocked_by": 1,
    "unblocked_by_username": "admin",
    "unblocked_at": "2026-05-10T06:42:48.518282Z",
    "unblock_reason": "Postman cleanup",
    "failed_attempts": [
      {
        "timestamp": "2026-05-10T06:42:48.284002+00:00",
        "ip_address": "127.0.0.1",
        "device_id": "security-fail-3-95350672",
        "failure_reason": "بيانات الدخول غير صحيحة"
      },
      {
        "timestamp": "2026-05-10T06:42:47.809485+00:00",
        "ip_address": "127.0.0.1",
        "device_id": "security-fail-2-95350672",
        "failure_reason": "بيانات الدخول غير صحيحة"
      },
      {
        "timestamp": "2026-05-10T06:42:47.328270+00:00",
        "ip_address": "127.0.0.1",
        "device_id": "security-fail-1-95350672",
        "failure_reason": "بيانات الدخول غير صحيحة"
      }
    ],
    "ip_addresses": [
      "127.0.0.1"
    ],
    "user_agents": [
      "PostmanRuntime/7.39.1"
    ],
    "device_ids": [
      "security-fail-1-95350672",
      "security-fail-2-95350672",
      "security-fail-3-95350672"
    ]
  }
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Security block/attempt IDs must exist where used.
- Manual unblock requires a phone number and optional reason.
- Deactivate/unblock operations require active admin permissions.

### 129. 15A Failed Login 1 For Manual Unblock Block
**Flow:** `09 Dashboard Devices Ban Security`
**Description:** Intentional failed login to create authentication attempts/security block for dashboard security endpoints.
**Method:** `POST`
**URL:** `{{base_url}}/accounts/signin/`
**Authentication:** No bearer token required
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "username": "{{student_phone}}",
  "password": "WrongPass123",
  "device_id": "security-fail-4-{{scenario_suffix}}",
  "device_name": "Postman Failed Login Device"
}
```
**Tested Response:** `400 Bad Request`

```json
{
  "error": "بيانات الدخول غير صحيحة. لديك عدد (2) محاولات متبقية",
  "remaining_attempts": 2,
  "warning": "بيانات الدخول غير صحيحة. لديك عدد (2) محاولات متبقية"
}
```
**Validations And Error Cases:**
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `username` and `password` are required.
- Student account must not be banned.
- Failed attempts are tracked and may create a `SecurityBlock`.
- Device token/session is created or refreshed; device limits may remove old devices.

### 130. 15A Failed Login 2 For Manual Unblock Block
**Flow:** `09 Dashboard Devices Ban Security`
**Description:** Intentional failed login to create authentication attempts/security block for dashboard security endpoints.
**Method:** `POST`
**URL:** `{{base_url}}/accounts/signin/`
**Authentication:** No bearer token required
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "username": "{{student_phone}}",
  "password": "WrongPass123",
  "device_id": "security-fail-5-{{scenario_suffix}}",
  "device_name": "Postman Failed Login Device"
}
```
**Tested Response:** `400 Bad Request`

```json
{
  "error": "بيانات الدخول غير صحيحة. لديك عدد (1) محاولات متبقية",
  "remaining_attempts": 1,
  "warning": "بيانات الدخول غير صحيحة. لديك عدد (1) محاولات متبقية"
}
```
**Validations And Error Cases:**
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `username` and `password` are required.
- Student account must not be banned.
- Failed attempts are tracked and may create a `SecurityBlock`.
- Device token/session is created or refreshed; device limits may remove old devices.

### 131. 15A Failed Login 3 Creates Manual Unblock Block
**Flow:** `09 Dashboard Devices Ban Security`
**Description:** Intentional failed login to create authentication attempts/security block for dashboard security endpoints.
**Method:** `POST`
**URL:** `{{base_url}}/accounts/signin/`
**Authentication:** No bearer token required
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "username": "{{student_phone}}",
  "password": "WrongPass123",
  "device_id": "security-fail-6-{{scenario_suffix}}",
  "device_name": "Postman Failed Login Device"
}
```
**Tested Response:** `403 Forbidden`

```json
{
  "error": "تم حظر محاولات تسجيل الدخول لهذا الرقم مؤقتاً بسبب تجاوز عدد المحاولات المسموحة. سيتم رفع الحظر تلقائياً بعد 14 دقيقة. إذا لم تكن أنت من قام بهذه المحاولات، يرجى التواصل مع الدعم الفني فوراً.",
  "error_code": "account_blocked",
  "blocked_until": "2026-05-10T06:57:49.959683Z",
  "remaining_seconds": 899,
  "remaining_time": "14 دقيقة",
  "block_level": 1
}
```
**Validations And Error Cases:**
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- `username` and `password` are required.
- Student account must not be banned.
- Failed attempts are tracked and may create a `SecurityBlock`.
- Device token/session is created or refreshed; device limits may remove old devices.

### 132. 16 Manual Unblock Phone
**Flow:** `09 Dashboard Devices Ban Security`
**Method:** `POST`
**URL:** `{{base_url}}/accounts/dashboard/security/unblock/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "phone_number": "{{student_phone}}",
  "reason": "Postman manual unblock"
}
```
**Tested Response:** `200 OK`

```json
{
  "success": true,
  "message": "تم رفع الحظر بنجاح عن 1 عملية/عمليات حظر",
  "phone_number": "01095350672",
  "unblocked_count": 1
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Security block/attempt IDs must exist where used.
- Manual unblock requires a phone number and optional reason.
- Deactivate/unblock operations require active admin permissions.

### 133. 17 Authentication Attempts List
**Flow:** `09 Dashboard Devices Ban Security`
**Method:** `GET`
**URL:** `{{base_url}}/accounts/dashboard/security/attempts/?phone_number={{student_phone}}`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 10,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 64,
      "phone_number": "01095350672",
      "attempt_type": "login",
      "attempt_type_display": "Login Attempt",
      "result": "failed",
      "result_display": "Failed",
      "attempted_at": "2026-05-10T06:42:49.948745Z",
      "ip_address": "127.0.0.1",
      "user_agent": "PostmanRuntime/7.39.1",
      "device_id": "security-fail-6-95350672",
      "failure_reason": "بيانات الدخول غير صحيحة",
      "related_block": null
    },
    {
      "id": 63,
      "phone_number": "01095350672",
      "attempt_type": "login",
      "attempt_type_display": "Login Attempt",
      "result": "failed",
      "result_display": "Failed",
      "attempted_at": "2026-05-10T06:42:49.470928Z",
      "ip_address": "127.0.0.1",
      "user_agent": "PostmanRuntime/7.39.1",
      "device_id": "security-fail-5-95350672",
      "failure_reason": "بيانات الدخول غير صحيحة",
      "related_block": null
    },
    {
      "id": 62,
      "phone_number": "01095350672",
      "attempt_type": "login",
      "attempt_type_display": "Login Attempt",
      "result": "failed",
      "result_display": "Failed",
      "attempted_at": "2026-05-10T06:42:49.012059Z",
      "ip_address": "127.0.0.1",
      "user_agent": "PostmanRuntime/7.39.1",
      "device_id": "security-fail-4-95350672",
      "failure_reason": "بيانات الدخول غير صحيحة",
      "related_block": null
    },
    {
      "id": 61,
      "phone_number": "01095350672",
      "attempt_type": "login",
      "attempt_type_display": "Login Attempt",
      "result": "failed",
      "result_display": "Failed",
      "attempted_at": "2026-05-10T06:42:48.284002Z",
      "ip_address": "127.0.0.1",
      "user_agent": "PostmanRuntime/7.39.1",
      "device_id": "s
... truncated for documentation ...
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- Security block/attempt IDs must exist where used.
- Manual unblock requires a phone number and optional reason.
- Deactivate/unblock operations require active admin permissions.

### 134. 18 Authentication Attempt Detail
**Flow:** `09 Dashboard Devices Ban Security`
**Method:** `GET`
**URL:** `{{base_url}}/accounts/dashboard/security/attempts/{{auth_attempt_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "id": 64,
  "phone_number": "01095350672",
  "attempt_type": "login",
  "attempt_type_display": "Login Attempt",
  "result": "failed",
  "result_display": "Failed",
  "attempted_at": "2026-05-10T06:42:49.948745Z",
  "ip_address": "127.0.0.1",
  "user_agent": "PostmanRuntime/7.39.1",
  "device_id": "security-fail-6-95350672",
  "failure_reason": "بيانات الدخول غير صحيحة",
  "related_block": null
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Security block/attempt IDs must exist where used.
- Manual unblock requires a phone number and optional reason.
- Deactivate/unblock operations require active admin permissions.

### 135. 19 Security Stats
**Flow:** `09 Dashboard Devices Ban Security`
**Method:** `GET`
**URL:** `{{base_url}}/accounts/dashboard/security/stats/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "total_blocks": 9,
  "active_blocks": 1,
  "blocks_today": 9,
  "blocks_this_week": 9,
  "total_attempts": 64,
  "failed_attempts_today": 34,
  "blocked_attempts_today": 0,
  "top_blocked_numbers": [
    {
      "phone_number": "01094917534",
      "block_count": 2
    },
    {
      "phone_number": "01095069128",
      "block_count": 2
    },
    {
      "phone_number": "01095211654",
      "block_count": 2
    },
    {
      "phone_number": "01095350672",
      "block_count": 2
    },
    {
      "phone_number": "wrong",
      "block_count": 1
    }
  ],
  "block_types_distribution": {
    "login": 9
  }
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- Security block/attempt IDs must exist where used.
- Manual unblock requires a phone number and optional reason.
- Deactivate/unblock operations require active admin permissions.

### 136. 20 Phone Security History
**Flow:** `09 Dashboard Devices Ban Security`
**Method:** `GET`
**URL:** `{{base_url}}/accounts/dashboard/security/phone/{{student_phone}}/history/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "phone_number": "01095350672",
  "current_status": null,
  "statistics": {
    "total_blocks": 2,
    "active_blocks": 0,
    "failed_attempts": 6,
    "successful_attempts": 4
  },
  "blocks": [
    {
      "id": 9,
      "phone_number": "01095350672",
      "block_type": "login",
      "block_type_display": "Failed Login Attempts",
      "blocked_at": "2026-05-10T06:42:49.960519Z",
      "blocked_until": "2026-05-10T06:57:49.959683Z",
      "block_level": 1,
      "consecutive_blocks": 1,
      "is_active": false,
      "is_expired": false,
      "remaining_seconds": 0,
      "remaining_formatted": "انتهت مدة الحظر",
      "manually_unblocked": true,
      "unblocked_by": 1,
      "unblocked_by_username": "admin",
      "unblocked_at": "2026-05-10T06:42:50.039691Z",
      "unblock_reason": "Postman manual unblock",
      "failed_attempts": [
        {
          "timestamp": "2026-05-10T06:42:49.948745+00:00",
          "ip_address": "127.0.0.1",
          "device_id": "security-fail-6-95350672",
          "failure_reason": "بيانات الدخول غير صحيحة"
        },
        {
          "timestamp": "2026-05-10T06:42:49.470928+00:00",
          "ip_address": "127.0.0.1",
          "device_id": "security-fail-5-95350672",
          "failure_reason": "بيانات الدخول غير صحيحة"
        },
        {
          "timestamp": "2026-05-10T06:42:49.012059+00:00",
          "ip_address": "127.0.0.1",
          "device_id": "security-fail-4-95350672",
          "failure_reason": "بيانات الدخول غير صحيحة"
        }
      ],
      "ip_addresses": [
        "127.0.0.1"
      ],
      "user_agents": [
        "PostmanRuntime/7.39.1"
      ],
      "device_ids": [
        "security-fail-5-95350672",
        "security-fail-6-95350672",
        "security-fail-4-95350672"
      ]
    },
    {
... truncated for documentation ...
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- Security block/attempt IDs must exist where used.
- Manual unblock requires a phone number and optional reason.
- Deactivate/unblock operations require active admin permissions.

## 10 Dashboard Deleted User Archive Restore

### 137. 01 Delete Managed Student And Archive
**Flow:** `10 Dashboard Deleted User Archive Restore`
**Method:** `DELETE`
**URL:** `{{base_url}}/accounts/dashboard/users/delete/{{managed_student_user_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "reason": "Postman archive/restore test"
}
```
**Tested Response:** `200 OK`

```json
{
  "success": true,
  "message": "تم حذف المستخدم Managed Student Updated 95350672 وحفظ بياناته في الأرشيف",
  "archive_id": 6
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.
- Target user must exist.
- Deletion creates a `DeletedUserArchive` snapshot.
- Protected/admin constraints may reject invalid deletion attempts.

### 138. 02 List Deleted Users
**Flow:** `10 Dashboard Deleted User Archive Restore`
**Method:** `GET`
**URL:** `{{base_url}}/accounts/dashboard/deleted-users/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "count": 6,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 6,
      "original_user_id": 19,
      "username": "01195350672",
      "name": "Managed Student Updated 95350672",
      "email": "",
      "user_type": "student",
      "parent_phone": "01222222222",
      "government": "1",
      "was_banned": false,
      "ban_reason": null,
      "original_created_at": "2026-05-10T06:42:32.850216Z",
      "deleted_at": "2026-05-10T06:42:50.423530Z",
      "is_restored": false,
      "deleted_by": 1,
      "deleted_by_username": "admin",
      "deleted_by_name": "Main Admin",
      "deletion_reason": "Postman archive/restore test",
      "user_data_snapshot": {
        "username": "01195350672",
        "name": "Managed Student Updated 95350672",
        "email": "",
        "user_type": "student",
        "parent_phone": "01222222222",
        "government": "1",
        "max_allowed_devices": 2,
        "is_banned": false,
        "ban_reason": null,
        "created_at": "2026-05-10T06:42:32.850216+00:00"
      }
    },
    {
      "id": 5,
      "original_user_id": 13,
      "username": "01095211654",
      "name": "Mariam EST Updated 95211654",
      "email": "",
      "user_type": "student",
      "parent_phone": "01111111111",
      "government": "1",
      "was_banned": false,
      "ban_reason": "",
      "original_created_at": "2026-05-10T06:40:13.316205Z",
      "deleted_at": "2026-05-10T06:40:35.173572Z",
      "is_restored": false,
      "deletion_reason": "حذف ذاتي من قبل المستخدم (Self-deletion)",
      "user_data_snapshot": {
        "id": 13,
        "username": "01095211654",
        "name": "Mariam EST Updated 95211654",
        "email": "",
        "user_type": "student",
        "parent_phone": "01111111111",
        "government"
... truncated for documentation ...
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.

### 139. 03 Deleted User Detail
**Flow:** `10 Dashboard Deleted User Archive Restore`
**Method:** `GET`
**URL:** `{{base_url}}/accounts/dashboard/deleted-users/{{deleted_archive_id}}/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** None declared in collection
**Body Type:** `None`
**Body Example:**

No request body.
**Tested Response:** `200 OK`

```json
{
  "id": 6,
  "original_user_id": 19,
  "username": "01195350672",
  "name": "Managed Student Updated 95350672",
  "email": "",
  "user_type": "student",
  "parent_phone": "01222222222",
  "government": "1",
  "was_banned": false,
  "ban_reason": null,
  "original_created_at": "2026-05-10T06:42:32.850216Z",
  "deleted_at": "2026-05-10T06:42:50.423530Z",
  "is_restored": false,
  "deleted_by": 1,
  "deleted_by_username": "admin",
  "deleted_by_name": "Main Admin",
  "deletion_reason": "Postman archive/restore test",
  "user_data_snapshot": {
    "username": "01195350672",
    "name": "Managed Student Updated 95350672",
    "email": "",
    "user_type": "student",
    "parent_phone": "01222222222",
    "government": "1",
    "max_allowed_devices": 2,
    "is_banned": false,
    "ban_reason": null,
    "created_at": "2026-05-10T06:42:32.850216+00:00"
  }
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `404 Not Found` when a path ID does not exist.

### 140. 04 Restore Deleted User
**Flow:** `10 Dashboard Deleted User Archive Restore`
**Method:** `POST`
**URL:** `{{base_url}}/accounts/dashboard/deleted-users/restore/`
**Authentication:** Bearer token: `{{admin_access_token}}`
**Headers:** `Content-Type: application/json`
**Body Type:** `JSON`
**Body Example:**

```json
{
  "archive_id": "{{deleted_archive_id}}",
  "password": "RestoredPass123"
}
```
**Tested Response:** `201 Created`

```json
{
  "success": true,
  "message": "تم استعادة المستخدم Managed Student Updated 95350672 بنجاح",
  "data": {
    "user_id": 20,
    "username": "01195350672",
    "name": "Managed Student Updated 95350672",
    "password": "RestoredPass123",
    "password_note": "كلمة المرور المخصصة",
    "original_archive_id": "6"
  }
}
```
**Validations And Error Cases:**
- `401 Unauthorized` when the bearer token is missing, expired, invalid, or removed by device/session controls.
- `403 Forbidden` when the authenticated user is not staff/admin.
- `400 Bad Request` for invalid JSON, invalid field type, missing required fields, or serializer validation errors.
- Archive ID or username fields required by endpoint must identify a deleted archive.
- Already restored users cannot be restored again.
- Restored username must not conflict with an active user.
