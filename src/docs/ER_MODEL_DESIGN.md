# American TEST ER Model Design

This document is a manager-facing ER design for the American TEST platform. It focuses on the real business domain: students subscribe to plans, choose allowed courses, and access course/unit exams. Staff users manage courses, units, plans, questions, exams, results, devices, bans, and security controls.

## Scope Notes

- There are no teachers, academic years, divisions, lessons, videos, or profile images in this data model.
- A `User` can be a student or an admin/staff user.
- A student is represented by `Student`, which is a one-to-one extension of `User`.
- Plans use day/month availability windows only. The effective year is calculated at runtime.
- A paid plan subscription grants access only to the selected courses, up to the plan course limit.
- Exams and questions can be related to a course directly or to a unit under a course.
- Students can take assigned course/unit exams, create temporary practice exams from their student bank, and create custom exams from the admin question bank.

## High-Level Domain Map

```mermaid
erDiagram
    USER ||--o| STUDENT : "student profile"
    USER ||--o{ USER_DEVICE : "uses"
    USER ||--o{ OTP : "receives"
    USER ||--o{ DELETED_USER_ARCHIVE : "admin deletes"
    USER ||--o{ SECURITY_BLOCK : "admin unblocks"

    STUDENT ||--o{ PLAN_SUBSCRIPTION : "buys"
    PLAN ||--o{ PLAN_SUBSCRIPTION : "is subscribed"
    PLAN_SUBSCRIPTION ||--o{ PLAN_SUBSCRIPTION_COURSE : "selects"
    COURSE ||--o{ PLAN_SUBSCRIPTION_COURSE : "included in"
    PLAN_SUBSCRIPTION ||--o{ COURSE_SUBSCRIPTION : "syncs access"
    COURSE ||--o{ COURSE_SUBSCRIPTION : "grants access"

    COURSE ||--o{ UNIT : "contains"
    COURSE ||--o{ EXAM : "has"
    UNIT ||--o{ EXAM : "has"
    COURSE ||--o{ QUESTION : "has"
    UNIT ||--o{ QUESTION : "has"

    EXAM ||--o{ EXAM_QUESTION : "contains"
    QUESTION ||--o{ EXAM_QUESTION : "assigned to"
    STUDENT ||--o{ RESULT : "takes"
    EXAM ||--o{ RESULT : "generates"
    RESULT ||--o{ RESULT_TRIAL : "has attempts"
```

## Accounts And Security

```mermaid
erDiagram
    USER {
        int id PK
        string username UK "phone number"
        string name
        string email
        string user_type "student/admin"
        string parent_phone
        string government
        int max_allowed_devices
        boolean is_banned
        datetime banned_at
        text ban_reason
        boolean is_staff
        boolean is_superuser
        datetime created_at
    }

    STUDENT {
        int id PK
        int user_id FK UK
        string name
        string parent_phone
        string code UK
        datetime created_at
    }

    USER_DEVICE {
        int id PK
        int user_id FK
        string device_token UK
        string device_id
        string device_name
        string ip_address
        text user_agent
        json device_info
        datetime logged_in_at
        datetime last_used_at
        boolean is_active
        boolean is_banned
        datetime banned_at
        text ban_reason
    }

    OTP {
        int id PK
        string phone_number
        string otp_code
        string purpose
        int user_id FK
        datetime created_at
        datetime expires_at
        boolean is_verified
        datetime verified_at
        boolean is_used
        datetime used_at
        int verification_attempts
    }

    SECURITY_BLOCK {
        int id PK
        string phone_number
        string block_type
        datetime blocked_at
        datetime blocked_until
        int block_level
        int consecutive_blocks
        boolean is_active
        boolean manually_unblocked
        int unblocked_by_id FK
        datetime unblocked_at
        text unblock_reason
        json failed_attempts
        json ip_addresses
        json user_agents
        json device_ids
    }

    AUTHENTICATION_ATTEMPT {
        int id PK
        string phone_number
        string attempt_type
        string result
        datetime attempted_at
        string ip_address
        text user_agent
        string device_id
        text failure_reason
        int related_block_id FK
    }

    DELETED_USER_ARCHIVE {
        int id PK
        int original_user_id
        string username
        string name
        string email
        string user_type
        string parent_phone
        string government
        boolean was_banned
        text ban_reason
        datetime original_created_at
        datetime deleted_at
        boolean is_restored
        int deleted_by_id FK
        text deletion_reason
        json user_data_snapshot
    }

    USER ||--o| STUDENT : "has student profile"
    USER ||--o{ USER_DEVICE : "has devices"
    USER ||--o{ OTP : "receives OTPs"
    USER ||--o{ DELETED_USER_ARCHIVE : "deleted by admin"
    USER ||--o{ SECURITY_BLOCK : "unblocked by admin"
    SECURITY_BLOCK ||--o{ AUTHENTICATION_ATTEMPT : "blocks attempts"
```

## Plans, Courses, And Access

```mermaid
erDiagram
    PLAN {
        int id PK
        string title
        decimal price
        int start_day
        int start_month
        int end_day
        int end_month
        int number_of_allowed_courses_to_subscribe
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    PLAN_SUBSCRIPTION {
        int id PK
        int student_id FK
        int plan_id FK
        string payment_status
        string easypay_invoice_uid
        string easypay_invoice_sequence
        url easypay_payment_url
        json easypay_payload
        datetime paid_at
        datetime created_at
        datetime updated_at
    }

    PLAN_SUBSCRIPTION_COURSE {
        int id PK
        int subscription_id FK
        int course_id FK
        datetime created_at
    }

    COURSE_SUBSCRIPTION {
        int id PK
        int student_id FK
        int course_id FK
        int plan_subscription_id FK
        boolean active
        datetime created_at
    }

    COURSE {
        int id PK
        string name
        text description
        image image
        int order
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    UNIT {
        int id PK
        int course_id FK
        string name
        text description
        int order
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    FILE {
        int id PK
        int unit_id FK
        string title
        file file
        datetime created_at
    }

    STUDENT ||--o{ PLAN_SUBSCRIPTION : "subscribes"
    PLAN ||--o{ PLAN_SUBSCRIPTION : "sold as"
    PLAN_SUBSCRIPTION ||--o{ PLAN_SUBSCRIPTION_COURSE : "selected courses"
    COURSE ||--o{ PLAN_SUBSCRIPTION_COURSE : "selected in"
    PLAN_SUBSCRIPTION ||--o{ COURSE_SUBSCRIPTION : "creates access rows"
    STUDENT ||--o{ COURSE_SUBSCRIPTION : "has access"
    COURSE ||--o{ COURSE_SUBSCRIPTION : "accessible course"
    COURSE ||--o{ UNIT : "contains"
    UNIT ||--o{ FILE : "has files"
```

## Exam Authoring

```mermaid
erDiagram
    EXAM {
        int id PK
        string title
        text description
        string related_to "COURSE/UNIT"
        int course_id FK
        int unit_id FK
        int number_of_questions
        int time_limit
        float score
        int passing_percent
        datetime start
        datetime end
        int number_of_allowed_trials
        string type "MANUAL/RANDOM/BANK"
        int easy_questions_count
        int medium_questions_count
        int hard_questions_count
        boolean show_answers_after_finish
        int order
        boolean is_active
        datetime allow_show_results_at
        datetime allow_show_answers_at
    }

    QUESTION_CATEGORY {
        int id PK
        string title
    }

    QUESTION {
        int id PK
        text text
        image image
        int points
        string difficulty
        int category_id FK
        int course_id FK
        int unit_id FK
        boolean is_active
        datetime created
        string question_type "MCQ/ESSAY"
        text comment
        string explanation
    }

    ANSWER {
        int id PK
        int question_id FK
        text text
        image image
        boolean is_correct
        datetime created
    }

    EXAM_QUESTION {
        int id PK
        int exam_id FK
        int question_id FK
        boolean is_active
        int order
        datetime created
        datetime updated
    }

    RANDOM_EXAM_BANK {
        int id PK
        int exam_id FK
    }

    EXAM_MODEL {
        int id PK
        int exam_id FK
        string title
        datetime created
        boolean is_active
    }

    EXAM_MODEL_QUESTION {
        int id PK
        int exam_model_id FK
        int question_id FK
        boolean is_active
    }

    ADMIN_QUESTION_BANK {
        int id PK
        int question_id FK
        datetime created
    }

    COURSE ||--o{ EXAM : "course exams"
    UNIT ||--o{ EXAM : "unit exams"
    COURSE ||--o{ QUESTION : "course questions"
    UNIT ||--o{ QUESTION : "unit questions"
    QUESTION_CATEGORY ||--o{ QUESTION : "categorizes"
    QUESTION ||--o{ ANSWER : "has MCQ answers"
    EXAM ||--o{ EXAM_QUESTION : "manual/bank questions"
    QUESTION ||--o{ EXAM_QUESTION : "assigned"
    QUESTION }o--o{ QUESTION : "similar questions"
    EXAM ||--o| RANDOM_EXAM_BANK : "has random bank"
    RANDOM_EXAM_BANK }o--o{ QUESTION : "candidate questions"
    EXAM ||--o{ EXAM_MODEL : "has models"
    EXAM_MODEL ||--o{ EXAM_MODEL_QUESTION : "contains"
    QUESTION ||--o{ EXAM_MODEL_QUESTION : "model question"
    QUESTION ||--o{ ADMIN_QUESTION_BANK : "available for student-created exams"
```

## Student Exam Activity

```mermaid
erDiagram
    RESULT {
        int id PK
        int student_id FK
        int exam_id FK
        int trial
        datetime added
        int exam_model_id FK
    }

    RESULT_TRIAL {
        int id PK
        int result_id FK
        int trial
        float score
        float exam_score
        int exam_model_id FK
        datetime student_started_exam_at
        datetime student_submitted_exam_at
        string submit_type
    }

    SUBMISSION {
        int id PK
        int student_id FK
        int exam_id FK
        int question_id FK
        int selected_answer_id FK
        boolean is_correct
        boolean is_solved
        int result_trial_id FK
    }

    ESSAY_SUBMISSION {
        int id PK
        int student_id FK
        int exam_id FK
        int question_id FK
        text answer_text
        file answer_file
        float score
        boolean is_scored
        datetime created
        int result_trial_id FK
    }

    STUDENT_BANK {
        int id PK
        int student_id FK
        int question_id FK
        string add_reason
        boolean is_solved_now
        datetime created
    }

    TEMP_EXAM {
        int id PK
        int student_id FK
        int course_id FK
        int unit_id FK
        int number_of_questions
        int time_limit
        datetime created
        float result
        string selected_questions_type
    }

    TEMP_EXAM_ALLOWED_TIMES {
        int id PK
        int number_of_allowedtempexams_per_day
    }

    STUDENT_CREATED_EXAM {
        int id PK
        int student_id FK
        int course_id FK
        int unit_id FK
        int number_of_mcq_questions
        int number_of_essay_questions
        int time_limit
        datetime created
        float exam_score
        float result
    }

    STUDENT_FAVORITE {
        int id PK
        int student_id FK
        int content_type_id FK
        int object_id
        datetime created_at
    }

    STUDENT ||--o{ RESULT : "has results"
    EXAM ||--o{ RESULT : "has attempts"
    RESULT ||--o{ RESULT_TRIAL : "contains trials"
    EXAM_MODEL ||--o{ RESULT_TRIAL : "random model used"
    RESULT_TRIAL ||--o{ SUBMISSION : "MCQ answers"
    RESULT_TRIAL ||--o{ ESSAY_SUBMISSION : "essay answers"
    QUESTION ||--o{ SUBMISSION : "answered"
    ANSWER ||--o{ SUBMISSION : "selected"
    QUESTION ||--o{ ESSAY_SUBMISSION : "answered"
    STUDENT ||--o{ STUDENT_BANK : "practice bank"
    QUESTION ||--o{ STUDENT_BANK : "saved for practice"
    STUDENT ||--o{ TEMP_EXAM : "creates practice exams"
    COURSE ||--o{ TEMP_EXAM : "filtered by"
    UNIT ||--o{ TEMP_EXAM : "filtered by"
    STUDENT ||--o{ STUDENT_CREATED_EXAM : "creates custom exams"
    COURSE ||--o{ STUDENT_CREATED_EXAM : "filtered by"
    UNIT ||--o{ STUDENT_CREATED_EXAM : "filtered by"
    STUDENT ||--o{ STUDENT_FAVORITE : "favorites content"
```

## Access Rules Summary

| Rule | Data Involved |
|---|---|
| A student can subscribe to a plan and select courses up to the plan limit. | `Plan`, `PlanSubscription`, `PlanSubscriptionCourse` |
| Course access starts only when payment is paid/manual and the plan date window is currently active. | `PlanSubscription.payment_status`, `Plan.start_day/start_month/end_day/end_month`, `CourseSubscription.active` |
| A student loses access when the plan end date passes, even if they subscribed late. | Runtime plan availability calculation |
| Exams are visible/accessed only through selected paid course access. | `CourseSubscription`, `Exam.course`, `Exam.unit.course` |
| Admins create course/unit questions and attach them to manual/bank exams. | `Question`, `Answer`, `ExamQuestion` |
| Random exams use a random bank and optional models. | `RandomExamBank`, `ExamModel`, `ExamModelQuestion` |
| Wrong or unsolved student answers feed the student practice bank. | `Submission`, `EssaySubmission`, `StudentBank` |
| Students can generate practice exams from their own bank. | `StudentBank`, `TempExam` |
| Students can generate custom exams from the admin question bank. | `AdminQuestionBank`, `StudentCreatedExam` |
| Device limits, device bans, account bans, OTP, and security blocks are account-level controls. | `UserDevice`, `OTP`, `SecurityBlock`, `AuthenticationAttempt` |

## Review Notes

- The model intentionally keeps payments on `PlanSubscription`, not on courses or exams.
- `CourseSubscription` is a synchronized access/cache row derived from paid plan subscriptions.
- `Question.course` is automatically set from `Question.unit.course` when a question is unit-related.
- `Exam.course` is automatically set from `Exam.unit.course` for unit exams, making access checks easier.
- `TempExamAllowedTimes` is a singleton configuration table.
