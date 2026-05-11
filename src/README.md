# american_test

Django/DRF backend for plan-based course subscriptions and exams.

## Local Commands

```bash
python3 manage.py migrate
python3 manage.py test
python3 manage.py runserver 127.0.0.1:8000
```

## Main Routes

- `accounts/` - signup, OTP verification, signin, password reset, device management.
- `plans/` - student plan listing, subscription creation, and owned subscriptions.
- `courses/` - student course listing, units, and course exams.
- `exams/` - student exam start/submit/result endpoints.
- `dashboard/` - staff CRUD for plans, subscriptions, courses, units, questions, and exams.
- `api/webhook/easypay/` - EasyPay payment webhook.

See `docs/project_plan.md`, `docs/work_log.md`, and `docs/full_testing_scenario.md` for the implementation plan, completed work notes, and full endpoint testing flow.
