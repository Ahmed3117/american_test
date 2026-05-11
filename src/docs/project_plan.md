# American Test Build Plan

## Project Goal

Build a course-plan subscription website/API where students register, subscribe to a plan, pay for it, choose the allowed number of courses, and access exams for those selected courses only during the plan window.

## Existing Copied Code

- `accounts`: custom user, OTP signup/signin, multi-device JWT protection, account/admin utilities.
- `services`: BeOn SMS, OTP, EasyPay/Fawry helpers, security services.
- `exam`: exam, question, answer, result, trial, student bank, and temporary exam logic copied from an older course app.
- `dashboard`: copied dashboard code was partial and still referenced old apps; it has been narrowed to the plan/course/exam product.
- `core`: Django settings/URLs copied from another project and still referenced missing apps.

## Architecture Decisions

- Keep the existing custom `accounts.User` model and OTP/device authentication flow.
- Add a `student.Student` profile linked one-to-one to `accounts.User` because the copied exam app expects `request.user.student`.
- Add a `course` app with `Course` and `Unit` only. The project has no academic-year, teacher, division, lesson, or profile-image domain.
- Add a `subscription` app with `Plan`, `PlanSubscription`, `PlanSubscriptionCourse`, and `CourseSubscription`.
- Keep plan dates as month/day fields. Calendar year is used only internally to evaluate the active subscription window.
- Compute access dynamically from the current calendar cycle, so access expires automatically on the plan end date even if `CourseSubscription.active` was not cleaned by a cron job.
- Remove copied shop/order concepts and keep payment attached directly to plan subscriptions.

## Core User Flow

1. Student signs up/signs in through `accounts`.
2. Student lists all active/inactive plans and sees whether each plan has started and whether it is currently accessible.
3. Student subscribes to a plan and selects up to `number_of_allowed_courses_to_subscribe` courses.
4. System creates a pending `PlanSubscription`.
5. Payment is started through EasyPay/Fawry when credentials are configured; otherwise the API returns a pending subscription without pretending payment succeeded.
6. When payment is confirmed, `PlanSubscription.mark_paid()` creates/updates `CourseSubscription` records.
7. Exam start checks course access against active paid plan subscriptions and the current plan end date.

## Main API Areas

- Public/student:
  - `GET /plans/`
  - `POST /plans/<id>/subscribe/`
  - `GET /plans/my-subscriptions/`
  - `GET /courses/`
  - `GET /courses/<id>/`
  - `GET /courses/<id>/exams/`
  - existing exam endpoints under `/exams/`
- Dashboard/staff:
  - `GET/POST /dashboard/plans/`
  - `GET/PATCH/DELETE /dashboard/plans/<id>/`
  - `GET/POST /dashboard/courses/`
  - `GET/PATCH/DELETE /dashboard/courses/<id>/`
  - `GET/POST /dashboard/courses/<course_id>/units/`
  - `GET/POST /dashboard/exams/`
  - `GET/PATCH/DELETE /dashboard/exams/<id>/`

## Remaining Follow-Up Work

- Add frontend pages/forms if this repository is intended to include the browser UI, not only the API.
- Confirm EasyPay webhook payload format for plan subscriptions against the real provider response.
- Add cron/management command to deactivate stale compatibility `CourseSubscription.active` rows for easier admin reporting, even though runtime access already checks dates dynamically.
- Continue adding focused workflow tests around student-created exams and payment confirmation paths.
