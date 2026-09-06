from .models import PlanSubscription


def get_student_from_user(user):
    return getattr(user, "student", None)


def get_accessible_course_ids_for_student(student):
    if not student:
        return set()

    course_ids = set()
    subscriptions = (
        PlanSubscription.objects.filter(
            student=student,
            payment_status__in=[
                PlanSubscription.PAYMENT_PAID,
                PlanSubscription.PAYMENT_MANUAL,
            ],
            plan__is_active=True,
        )
        .select_related("plan")
        .prefetch_related("courses")
    )
    for subscription in subscriptions:
        if subscription.has_access_now:
            course_ids.update(course.id for course in subscription.courses.all())
    return course_ids


def student_has_course_access(student, course):
    if not student or not course:
        return False
    subscriptions = (
        PlanSubscription.objects.filter(
            student=student,
            courses=course,
            payment_status__in=[
                PlanSubscription.PAYMENT_PAID,
                PlanSubscription.PAYMENT_MANUAL,
            ],
            plan__is_active=True,
        )
        .select_related("plan")
        .distinct()
    )
    return any(subscription.has_access_now for subscription in subscriptions)


def user_has_course_access(user, course):
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    return student_has_course_access(get_student_from_user(user), course)
