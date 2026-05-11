# Full Postman Testing Scenario

This document provides a comprehensive step-by-step testing guide using Postman to test all API endpoints and flows in the American Test platform.

---

## Table of Contents

1. [Environment Setup](#1-environment-setup)
2. [Authentication & User Management](#2-authentication--user-management)
3. [Course & Unit Management](#3-course--unit-management)
4. [Question & Answer Management](#4-question--answer-management)
5. [Exam Management](#5-exam-management)
6. [Plan & Subscription Management](#6-plan--subscription-management)
7. [Student Exam Flow](#7-student-exam-flow)
8. [Security & Device Management](#8-security--device-management)
9. [Admin Dashboard Reports](#9-admin-dashboard-reports)

---

## 1. Environment Setup

### Postman Environment Variables

Create a Postman environment with these variables:

```
BASE_URL: http://localhost:9000
ADMIN_TOKEN: (will be set after admin login)
STUDENT_TOKEN: (will be set after student login)
ADMIN_USERNAME: admin
ADMIN_PASSWORD: AdminPass123
STUDENT_USERNAME: 01012345678
STUDENT_PASSWORD: StudentPass123
```

### Collection Setup

Create a collection named `American Test API` with folders for each section.

---

## 2. Authentication & User Management

### 2.1 Admin Dashboard Login

**Request:**
```
POST {{BASE_URL}}/accounts/dashboard/signin/
Content-Type: application/json

{
    "username": "{{ADMIN_USERNAME}}",
    "password": "{{ADMIN_PASSWORD}}"
}
```

**Save to variable:**
- Response → `access` token → `ADMIN_TOKEN`

**Expected:** `200 OK` with `access` and `refresh` tokens

---

### 2.2 Create New Admin User

**Request:**
```
POST {{BASE_URL}}/accounts/dashboard/create-admin-user/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "username": "operations",
    "password": "OpsPass123",
    "name": "Operations Manager",
    "email": "ops@americantest.com"
}
```

**Expected:** `201 Created`

---

### 2.3 List All Admins

**Request:**
```
GET {{BASE_URL}}/accounts/dashboard/admins/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK` with list of admin users

---

### 2.4 Student Signup - Request OTP

**Request:**
```
POST {{BASE_URL}}/accounts/signup/
Content-Type: application/json

{
    "username": "01012345678",
    "password": "StudentPass123",
    "name": "Ahmed Student",
    "user_type": "student",
    "parent_phone": "01111111111",
    "government": "1"
}
```

**Expected:** `200 OK`
```json
{
    "success": true,
    "message": "تم إرسال رمز التحقق إلى رقم هاتفك",
    "phone_number": "01012345678",
    "expires_in_minutes": 10
}
```

---

### 2.5 Get OTP from Database

Since OTP is sent via SMS (BeOn service), for testing you'll need to check the database or logs:

```python
# Run in Django shell
python manage.py shell
from accounts.models import OTP
otp = OTP.objects.filter(phone_number='01012345678', purpose='signup').last()
print(f"OTP: {otp.otp_code}")
```

---

### 2.6 Verify Signup OTP

**Request:**
```
POST {{BASE_URL}}/accounts/signup/verify-otp/
Content-Type: application/json

{
    "username": "01012345678",
    "password": "StudentPass123",
    "name": "Ahmed Student",
    "otp_code": "123456",
    "user_type": "student",
    "parent_phone": "01111111111",
    "government": "1",
    "device_id": "test-device-001"
}
```

**Expected:** `201 Created` with JWT tokens
```json
{
    "refresh": "<refresh_token>",
    "access": "<access_token>"
}
```

**Save to variable:** Response → `access` → `STUDENT_TOKEN`

---

### 2.7 Student Login

**Request:**
```
POST {{BASE_URL}}/accounts/signin/
Content-Type: application/json

{
    "username": "01012345678",
    "password": "StudentPass123",
    "device_id": "test-device-001"
}
```

**Expected:** `200 OK` with JWT tokens

---

### 2.8 Get User Profile

**Request:**
```
GET {{BASE_URL}}/accounts/get-user-data/
Authorization: Bearer {{STUDENT_TOKEN}}
```

**Expected:** `200 OK` with user data

---

### 2.9 Update User Profile

**Request:**
```
PATCH {{BASE_URL}}/accounts/update-user-data/
Authorization: Bearer {{STUDENT_TOKEN}}
Content-Type: application/json

{
    "name": "Ahmed Updated Name",
    "email": "ahmed@email.com"
}
```

**Expected:** `200 OK`

---

### 2.10 Change Password

**Request:**
```
POST {{BASE_URL}}/accounts/change-password/
Authorization: Bearer {{STUDENT_TOKEN}}
Content-Type: application/json

{
    "old_password": "StudentPass123",
    "new_password": "NewStudentPass456"
}
```

**Expected:** `200 OK`

---

### 2.11 List My Devices

**Request:**
```
GET {{BASE_URL}}/accounts/my-devices/
Authorization: Bearer {{STUDENT_TOKEN}}
```

**Expected:** `200 OK` with list of devices

---

## 3. Course & Unit Management

### 3.1 Create Course

**Request:**
```
POST {{BASE_URL}}/dashboard/courses/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "name": "EST Math",
    "description": "American Test Mathematics Preparation",
    "image": null,
    "order": 1,
    "is_active": true
}
```

**Expected:** `201 Created`
**Save:** Response → `id` → `COURSE_ID`

---

### 3.2 Create Another Course

**Request:**
```
POST {{BASE_URL}}/dashboard/courses/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "name": "EST English",
    "description": "American Test English Preparation",
    "order": 2,
    "is_active": true
}
```

**Expected:** `201 Created`
**Save:** Response → `id` → `COURSE2_ID`

---

### 3.3 List Courses

**Request:**
```
GET {{BASE_URL}}/dashboard/courses/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK` with list of courses

---

### 3.4 Get Course Detail

**Request:**
```
GET {{BASE_URL}}/dashboard/courses/{{COURSE_ID}}/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK` with course details including units

---

### 3.5 Update Course

**Request:**
```
PATCH {{BASE_URL}}/dashboard/courses/{{COURSE_ID}}/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "name": "EST Math - Updated",
    "description": "Updated description"
}
```

**Expected:** `200 OK`

---

### 3.6 Create Unit

**Request:**
```
POST {{BASE_URL}}/dashboard/courses/{{COURSE_ID}}/units/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "name": "Algebra Foundations",
    "description": "Basic algebra concepts",
    "order": 1,
    "is_active": true
}
```

**Expected:** `201 Created`
**Save:** Response → `id` → `UNIT_ID`

---

### 3.7 Create Another Unit

**Request:**
```
POST {{BASE_URL}}/dashboard/courses/{{COURSE_ID}}/units/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "name": "Linear Equations",
    "description": "Solving linear equations",
    "order": 2,
    "is_active": true
}
```

**Expected:** `201 Created`
**Save:** Response → `id` → `UNIT2_ID`

---

### 3.8 Get Unit Detail

**Request:**
```
GET {{BASE_URL}}/dashboard/units/{{UNIT_ID}}/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK`

---

### 3.9 Update Unit

**Request:**
```
PATCH {{BASE_URL}}/dashboard/units/{{UNIT_ID}}/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "name": "Algebra Foundations - Updated"
}
```

**Expected:** `200 OK`

---

## 4. Question & Answer Management

### 4.1 Create Question Category

**Request:**
```
POST {{BASE_URL}}/dashboard/question-categories/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "title": "Algebra"
}
```

**Expected:** `201 Created`
**Save:** Response → `id` → `CATEGORY_ID`

---

### 4.2 Create Course-Level MCQ Question

**Request:**
```
POST {{BASE_URL}}/dashboard/questions/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: multipart/form-data

text: "If x + 5 = 10, what is x?"
points: 2
difficulty: EASY
category: {{CATEGORY_ID}}
course: {{COURSE_ID}}
question_type: MCQ

answers[0][text]: 5
answers[0][is_correct]: true
answers[1][text]: 3
answers[1][is_correct]: false
answers[2][text]: 7
answers[2][is_correct]: false
```

**Expected:** `201 Created`
**Save:** Response → `id` → `MCQ_QUESTION_1_ID`

---

### 4.3 Create Unit-Level MCQ Question

**Request:**
```
POST {{BASE_URL}}/dashboard/questions/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: multipart/form-data

text: "What is 2(x + 4)?"
points: 2
difficulty: MEDIUM
category: {{CATEGORY_ID}}
course: {{COURSE_ID}}
unit: {{UNIT_ID}}
question_type: MCQ

answers[0][text]: 2x + 8
answers[0][is_correct]: true
answers[1][text]: 2x + 4
answers[1][is_correct]: false
answers[2][text]: x + 8
answers[2][is_correct]: false
```

**Expected:** `201 Created`
**Save:** Response → `id` → `MCQ_QUESTION_2_ID`

---

### 4.4 Create Essay Question

**Request:**
```
POST {{BASE_URL}}/dashboard/questions/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: multipart/form-data

text: "Explain the steps to solve x + 5 = 10"
points: 5
difficulty: HARD
category: {{CATEGORY_ID}}
course: {{COURSE_ID}}
question_type: ESSAY
explanation: "Step 1: Subtract 5 from both sides. Step 2: x = 5"
```

**Expected:** `201 Created`
**Save:** Response → `id` → `ESSAY_QUESTION_ID`

---

### 4.5 Create Another MCQ Question

**Request:**
```
POST {{BASE_URL}}/dashboard/questions/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: multipart/form-data

text: "Which value satisfies x - 1 = 4?"
points: 2
difficulty: EASY
category: {{CATEGORY_ID}}
course: {{COURSE_ID}}
question_type: MCQ

answers[0][text]: 5
answers[0][is_correct]: true
answers[1][text]: 3
answers[1][is_correct]: false
answers[2][text]: 4
answers[2][is_correct]: false
```

**Expected:** `201 Created`
**Save:** Response → `id` → `MCQ_QUESTION_3_ID`

---

### 4.6 Get Question Count

**Request:**
```
GET {{BASE_URL}}/dashboard/questions/count/?course={{COURSE_ID}}
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK`
```json
{
    "count": 4,
    "active_count": 4,
    "mcq_count": 3,
    "essay_count": 1,
    "easy_count": 2,
    "medium_count": 1,
    "hard_count": 1
}
```

---

### 4.7 List Questions

**Request:**
```
GET {{BASE_URL}}/dashboard/questions/?course={{COURSE_ID}}
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK` with paginated list

---

### 4.8 Update Question

**Request:**
```
PATCH {{BASE_URL}}/dashboard/questions/{{MCQ_QUESTION_1_ID}}/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: multipart/form-data

text: "If x + 5 = 12, what is x?"
points: 3
```

**Expected:** `200 OK`

---

### 4.9 Bulk Create Questions

**Request:**
```
POST {{BASE_URL}}/dashboard/questions/bulk-create/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: multipart/form-data

exam_id: (empty for now)

questions[0][text]: "What is 3 + 3?"
questions[0][points]: 1
questions[0][difficulty]: EASY
questions[0][category]: {{CATEGORY_ID}}
questions[0][course]: {{COURSE_ID}}
questions[0][question_type]: MCQ
questions[0][answers][0][text]: 6
questions[0][answers][0][is_correct]: true
questions[0][answers][1][text]: 5
questions[0][answers][1][is_correct]: false

questions[1][text]: "What is 10 - 5?"
questions[1][points]: 1
questions[1][difficulty]: EASY
questions[1][category]: {{CATEGORY_ID}}
questions[1][course]: {{COURSE_ID}}
questions[1][question_type]: MCQ
questions[1][answers][0][text]: 5
questions[1][answers][0][is_correct]: true
questions[1][answers][1][text]: 6
questions[1][answers][1][is_correct]: false
```

**Expected:** `201 Created`

---

### 4.10 Add Similar Questions

**Request:**
```
POST {{BASE_URL}}/dashboard/questions/{{MCQ_QUESTION_1_ID}}/similars/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "question_ids": [{{MCQ_QUESTION_2_ID}}, {{MCQ_QUESTION_3_ID}}]
}
```

**Expected:** `200 OK`

---

## 5. Exam Management

### 5.1 Create Course-Level Exam (Manual)

**Request:**
```
POST {{BASE_URL}}/dashboard/exams/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "title": "EST Math Midterm",
    "description": "Midterm exam for EST Math course",
    "related_to": "COURSE",
    "course": {{COURSE_ID}},
    "type": "MANUAL",
    "number_of_questions": 2,
    "time_limit": 30,
    "passing_percent": 60,
    "number_of_allowed_trials": 3,
    "easy_questions_count": 1,
    "medium_questions_count": 1,
    "hard_questions_count": 0,
    "start": "2026-01-01T00:00:00Z",
    "end": "2027-12-31T23:59:59Z",
    "show_answers_after_finish": true,
    "is_active": true
}
```

**Expected:** `201 Created`
**Save:** Response → `id` → `EXAM_ID`

---

### 5.2 Add Questions to Manual Exam

**Request:**
```
POST {{BASE_URL}}/dashboard/exams/{{EXAM_ID}}/questions/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "question_ids": [{{MCQ_QUESTION_1_ID}}, {{ESSAY_QUESTION_ID}}]
}
```

**Expected:** `201 Created`

---

### 5.3 List Exam Questions

**Request:**
```
GET {{BASE_URL}}/dashboard/exams/{{EXAM_ID}}/questions/list/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK` with list of exam questions

---

### 5.4 Remove Question from Exam

**Request:**
```
DELETE {{BASE_URL}}/dashboard/exams/{{EXAM_ID}}/questions/{{MCQ_QUESTION_1_ID}}/remove/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK`

---

### 5.5 Re-add Question to Exam

**Request:**
```
POST {{BASE_URL}}/dashboard/exams/{{EXAM_ID}}/questions/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "question_ids": [{{MCQ_QUESTION_1_ID}}]
}
```

**Expected:** `201 Created`

---

### 5.6 Create Random Exam

**Request:**
```
POST {{BASE_URL}}/dashboard/exams/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "title": "EST Math Random Practice",
    "description": "Random questions from question bank",
    "related_to": "COURSE",
    "course": {{COURSE_ID}},
    "type": "RANDOM",
    "number_of_questions": 3,
    "time_limit": 20,
    "passing_percent": 50,
    "number_of_allowed_trials": 2,
    "easy_questions_count": 1,
    "medium_questions_count": 1,
    "hard_questions_count": 1,
    "start": "2026-01-01T00:00:00Z",
    "end": "2027-12-31T23:59:59Z",
    "is_active": true
}
```

**Expected:** `201 Created`
**Save:** Response → `id` → `RANDOM_EXAM_ID`

---

### 5.7 Add Questions to Random Exam Bank

**Request:**
```
POST {{BASE_URL}}/dashboard/exams/{{RANDOM_EXAM_ID}}/random-bank/add/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "question_ids": [{{MCQ_QUESTION_1_ID}}, {{MCQ_QUESTION_2_ID}}, {{MCQ_QUESTION_3_ID}}]
}
```

**Expected:** `201 Created`

---

### 5.8 Create Exam Model (for Random Exam)

**Request:**
```
POST {{BASE_URL}}/dashboard/exam-models/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "exam": {{RANDOM_EXAM_ID}},
    "title": "Model A - Easy Focus",
    "is_active": true
}
```

**Expected:** `201 Created`
**Save:** Response → `id` → `EXAM_MODEL_ID`

---

### 5.9 Add Questions to Exam Model

**Request:**
```
POST {{BASE_URL}}/dashboard/exams/{{RANDOM_EXAM_ID}}/models/{{EXAM_MODEL_ID}}/questions/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "question_ids": [{{MCQ_QUESTION_1_ID}}, {{MCQ_QUESTION_2_ID}}]
}
```

**Expected:** `200 OK`

---

### 5.10 Suggest Questions for Model

**Request:**
```
GET {{BASE_URL}}/dashboard/exams/{{RANDOM_EXAM_ID}}/suggest-model-questions/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK` with suggested questions

---

### 5.11 List Exam Models

**Request:**
```
GET {{BASE_URL}}/dashboard/exam-models/?exam={{RANDOM_EXAM_ID}}
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK` with list of exam models

---

### 5.12 Copy Exam

**Request:**
```
POST {{BASE_URL}}/dashboard/exams/{{EXAM_ID}}/copy/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "related_to": "COURSE",
    "course": {{COURSE_ID}}
}
```

**Expected:** `201 Created`
**Save:** Response → `id` → `COPIED_EXAM_ID`

---

### 5.13 Reorder Exam Questions

**Request:**
```
POST {{BASE_URL}}/dashboard/exam-questions/reorder/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

[
    {"exam_question": <exam_question_id_1>, "new_order": 2},
    {"exam_question": <exam_question_id_2>, "new_order": 1}
]
```

**Expected:** `200 OK`

---

### 5.14 List All Exams

**Request:**
```
GET {{BASE_URL}}/dashboard/exams/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK` with paginated list

---

### 5.15 Filter Exams by Status

**Request:**
```
GET {{BASE_URL}}/dashboard/exams/?status=active
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK` with filtered list

---

### 5.16 Update Exam

**Request:**
```
PATCH {{BASE_URL}}/dashboard/exams/{{EXAM_ID}}/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "time_limit": 45,
    "passing_percent": 70
}
```

**Expected:** `200 OK`

---

## 6. Plan & Subscription Management

### 6.1 Create Plan

**Request:**
```
POST {{BASE_URL}}/dashboard/plans/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "title": "EST Spring Access",
    "price": "1400.00",
    "start_day": 1,
    "start_month": 1,
    "end_day": 31,
    "end_month": 12,
    "number_of_allowed_courses_to_subscribe": 1,
    "is_active": true
}
```

**Expected:** `201 Created`
**Save:** Response → `id` → `PLAN_ID`

---

### 6.2 Create Future Plan

**Request:**
```
POST {{BASE_URL}}/dashboard/plans/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "title": "EST Summer Access",
    "price": "2000.00",
    "start_day": 1,
    "start_month": 6,
    "end_day": 31,
    "end_month": 8,
    "number_of_allowed_courses_to_subscribe": 2,
    "is_active": true
}
```

**Expected:** `201 Created`
**Save:** Response → `id` → `FUTURE_PLAN_ID`

---

### 6.3 Update Plan

**Request:**
```
PATCH {{BASE_URL}}/dashboard/plans/{{PLAN_ID}}/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "price": "1500.00"
}
```

**Expected:** `200 OK`

---

### 6.4 List Plans

**Request:**
```
GET {{BASE_URL}}/dashboard/plans/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK` with list of plans

---

### 6.5 Student Subscribe to Plan (Invalid - Too Many Courses)

**Request:**
```
POST {{BASE_URL}}/plans/{{PLAN_ID}}/subscribe/
Authorization: Bearer {{STUDENT_TOKEN}}
Content-Type: application/json

{
    "course_ids": [{{COURSE_ID}}, {{COURSE2_ID}}]
}
```

**Expected:** `400 Bad Request` (Plan only allows 1 course)

---

### 6.6 Student Subscribe to Plan (Valid)

**Request:**
```
POST {{BASE_URL}}/plans/{{PLAN_ID}}/subscribe/
Authorization: Bearer {{STUDENT_TOKEN}}
Content-Type: application/json

{
    "course_ids": [{{COURSE_ID}}]
}
```

**Expected:** `201 Created`
**Save:** Response → `id` → `SUBSCRIPTION_ID`

---

### 6.7 List Pending Subscriptions (Dashboard)

**Request:**
```
GET {{BASE_URL}}/dashboard/plans/subscriptions/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK` with pending subscription

---

### 6.8 Confirm Subscription (Manual)

**Request:**
```
POST {{BASE_URL}}/dashboard/plans/subscriptions/{{SUBSCRIPTION_ID}}/confirm/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK`

---

### 6.9 List My Subscriptions (Student)

**Request:**
```
GET {{BASE_URL}}/plans/my-subscriptions/
Authorization: Bearer {{STUDENT_TOKEN}}
```

**Expected:** `200 OK` with confirmed subscription

---

## 7. Student Exam Flow

### 7.1 List Courses (Student)

**Request:**
```
GET {{BASE_URL}}/courses/
Authorization: Bearer {{STUDENT_TOKEN}}
```

**Expected:** `200 OK` with list of courses

---

### 7.2 Get Course Detail (Student)

**Request:**
```
GET {{BASE_URL}}/courses/{{COURSE_ID}}/
Authorization: Bearer {{STUDENT_TOKEN}}
```

**Expected:** `200 OK` with course details

---

### 7.3 List Course Exams (Student)

**Request:**
```
GET {{BASE_URL}}/courses/{{COURSE_ID}}/exams/
Authorization: Bearer {{STUDENT_TOKEN}}
```

**Expected:** `200 OK` with exams for the subscribed course

---

### 7.4 Check Exam Start Ability

**Request:**
```
GET {{BASE_URL}}/exams/{{EXAM_ID}}/start-ability/
Authorization: Bearer {{STUDENT_TOKEN}}
```

**Expected:** `200 OK`
```json
{
    "status": "can_start"
}
```

---

### 7.5 Start Exam

**Request:**
```
GET {{BASE_URL}}/exams/{{EXAM_ID}}/start/
Authorization: Bearer {{STUDENT_TOKEN}}
```

**Expected:** `200 OK`
```json
{
    "exam_id": 1,
    "exam_title": "EST Math Midterm",
    "exam_time_limit": 30,
    "questions": [...],
    "resuming": false,
    "trial_id": 1
}
```

**Save:** Response → `trial_id` → `TRIAL_ID`

---

### 7.6 Submit Exam - MCQ Answer

**Request:**
```
POST {{BASE_URL}}/exams/{{EXAM_ID}}/submit/
Authorization: Bearer {{STUDENT_TOKEN}}
Content-Type: multipart/form-data

question_id_1: <id of MCQ question>
selected_answer_id_<answer_id>: <id of correct answer>

question_id_2: <id of essay question>
essay_answer_text_<essay_id>: "Step 1: Subtract 5 from both sides. Step 2: x = 5"
```

**Expected:** `200 OK`

---

### 7.7 List Exam Results (Student)

**Request:**
```
GET {{BASE_URL}}/exams/results/
Authorization: Bearer {{STUDENT_TOKEN}}
```

**Expected:** `200 OK` with list of results

---

### 7.8 Get Result Detail (Student)

**Request:**
```
GET {{BASE_URL}}/exams/results/<result_id>/
Authorization: Bearer {{STUDENT_TOKEN}}
```

**Expected:** `200 OK` with detailed result

---

### 7.9 List Essay Submissions (Dashboard)

**Request:**
```
GET {{BASE_URL}}/dashboard/essay-submissions/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK` with essay submissions

---

### 7.10 Score Essay (Dashboard)

**Request:**
```
POST {{BASE_URL}}/dashboard/essay-submissions/<submission_id>/score/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "score": 4
}
```

**Expected:** `200 OK`

---

## 8. Security & Device Management

### 8.1 Admin List Student Devices

**Request:**
```
GET {{BASE_URL}}/accounts/dashboard/students/devices/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK`

---

### 8.2 Update Student Max Devices

**Request:**
```
POST {{BASE_URL}}/accounts/dashboard/students/{{STUDENT_ID}}/max-devices/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "max_allowed_devices": 3
}
```

**Expected:** `200 OK`

---

### 8.3 Ban Student

**Request:**
```
POST {{BASE_URL}}/accounts/dashboard/students/{{STUDENT_ID}}/ban/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "reason": "Violation of terms of service"
}
```

**Expected:** `200 OK`

---

### 8.4 Unban Student

**Request:**
```
POST {{BASE_URL}}/accounts/dashboard/students/{{STUDENT_ID}}/unban/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK`

---

### 8.5 Security Statistics

**Request:**
```
GET {{BASE_URL}}/accounts/dashboard/security/stats/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK` with security statistics

---

### 8.6 Manual Unblock Phone

**Request:**
```
POST {{BASE_URL}}/accounts/dashboard/security/unblock/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "phone_number": "01012345678",
    "reason": "Customer support request"
}
```

**Expected:** `200 OK`

---

## 9. Admin Dashboard Reports

### 9.1 List Results

**Request:**
```
GET {{BASE_URL}}/dashboard/results/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK` with paginated results

---

### 9.2 Get Result Detail

**Request:**
```
GET {{BASE_URL}}/dashboard/results/{{RESULT_ID}}/detail/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK` with detailed result including all trials

---

### 9.3 List All Trials

**Request:**
```
GET {{BASE_URL}}/dashboard/trials/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK` with paginated trials

---

### 9.4 Students Who Took Exam

**Request:**
```
GET {{BASE_URL}}/dashboard/exams/{{EXAM_ID}}/students/took/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK` with list of students

---

### 9.5 Students Who Did NOT Take Exam

**Request:**
```
GET {{BASE_URL}}/dashboard/exams/{{EXAM_ID}}/students/not-took/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK` with list of students who haven't taken the exam

---

### 9.6 Exams Taken by Student

**Request:**
```
GET {{BASE_URL}}/dashboard/students/{{STUDENT_ID}}/exams/taken/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK` with list of exams taken

---

### 9.7 Exams NOT Taken by Student

**Request:**
```
GET {{BASE_URL}}/dashboard/students/{{STUDENT_ID}}/exams/not-taken/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK` with list of available exams not taken

---

### 9.8 Reduce Result Trial (Admin Reset)

**Request:**
```
POST {{BASE_URL}}/dashboard/results/{{RESULT_ID}}/reduce-trial/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK`

---

### 9.9 Create Temp Exam Allowed Times

**Request:**
```
POST {{BASE_URL}}/dashboard/temp-exam-allowed-times/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "number_of_allowedtempexams_per_day": 2
}
```

**Expected:** `200 OK`

---

### 9.10 Admin Question Bank - Add Questions

**Request:**
```
POST {{BASE_URL}}/dashboard/admin-question-bank/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "questions": [{{MCQ_QUESTION_1_ID}}, {{MCQ_QUESTION_2_ID}}]
}
```

**Expected:** `201 Created`

---

### 9.11 Admin Question Bank - Bulk Add

**Request:**
```
POST {{BASE_URL}}/dashboard/admin-question-bank/bulk/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "questions": [{{MCQ_QUESTION_3_ID}}]
}
```

**Expected:** `201 Created`

---

### 9.12 Admin Question Bank - List

**Request:**
```
GET {{BASE_URL}}/dashboard/admin-question-bank/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK` with list of questions in bank

---

### 9.13 Admin Question Bank - Delete

**Request:**
```
DELETE {{BASE_URL}}/dashboard/admin-question-bank/{{BANK_ITEM_ID}}/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `204 No Content`

---

### 9.14 Delete First Trial for Exam

**Request:**
```
DELETE {{BASE_URL}}/dashboard/exams/{{EXAM_ID}}/trials/delete-first/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `200 OK`

---

## Error Handling Tests

### Test Invalid Login

**Request:**
```
POST {{BASE_URL}}/accounts/signin/
Content-Type: application/json

{
    "username": "wrong_user",
    "password": "wrong_password"
}
```

**Expected:** `400 Bad Request`

---

### Test Unauthorized Access

**Request:**
```
GET {{BASE_URL}}/dashboard/plans/
```

**Expected:** `401 Unauthorized`

---

### Test Forbidden Access (Student accessing Admin endpoint)

**Request:**
```
POST {{BASE_URL}}/dashboard/plans/
Authorization: Bearer {{STUDENT_TOKEN}}
```

**Expected:** `403 Forbidden`

---

### Test Not Found

**Request:**
```
GET {{BASE_URL}}/dashboard/plans/99999/
Authorization: Bearer {{ADMIN_TOKEN}}
```

**Expected:** `404 Not Found`

---

### Test Validation Error

**Request:**
```
POST {{BASE_URL}}/dashboard/exams/
Authorization: Bearer {{ADMIN_TOKEN}}
Content-Type: application/json

{
    "title": "Test Exam",
    "related_to": "COURSE"
    "course": null
}
```

**Expected:** `400 Bad Request` with validation errors

---

## Quick Test Sequences

### Complete Admin Setup Sequence

```
1. POST /accounts/dashboard/signin/ (admin)
2. POST /dashboard/courses/ (create course)
3. POST /dashboard/courses/{id}/units/ (create unit)
4. POST /dashboard/question-categories/ (create category)
5. POST /dashboard/questions/ (create MCQ)
6. POST /dashboard/questions/ (create Essay)
7. POST /dashboard/exams/ (create exam)
8. POST /dashboard/exams/{id}/questions/ (add questions)
9. POST /dashboard/plans/ (create plan)
10. POST /dashboard/plans/subscriptions/{id}/confirm/ (confirm subscription)
```

### Complete Student Exam Sequence

```
1. POST /accounts/signup/ (request OTP)
2. GET OTP from database
3. POST /accounts/signup/verify-otp/ (verify)
4. POST /plans/{id}/subscribe/ (subscribe to plan)
5. POST /dashboard/plans/subscriptions/{id}/confirm/ (admin confirms)
6. GET /courses/ (list courses)
7. GET /courses/{id}/exams/ (list exams)
8. GET /exams/{id}/start-ability/ (check if can start)
9. GET /exams/{id}/start/ (start exam)
10. POST /exams/{id}/submit/ (submit answers)
11. GET /exams/results/ (view results)
```

---

## Postman Environment Export

```json
{
    "id": "american-test-env",
    "name": "American Test Environment",
    "values": [
        {"key": "BASE_URL", "value": "http://localhost:9000", "type": "default"},
        {"key": "ADMIN_TOKEN", "value": "", "type": "secret"},
        {"key": "STUDENT_TOKEN", "value": "", "type": "secret"},
        {"key": "ADMIN_USERNAME", "value": "admin", "type": "default"},
        {"key": "ADMIN_PASSWORD", "value": "AdminPass123", "type": "secret"},
        {"key": "STUDENT_USERNAME", "value": "01012345678", "type": "default"},
        {"key": "STUDENT_PASSWORD", "value": "StudentPass123", "type": "secret"}
    ],
    "timestamp": 1704067200000,
    "_postman_variable_scope": "environment"
}
```
