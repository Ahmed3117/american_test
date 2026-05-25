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
            course_ids.update(subscription.courses.values_list("id", flat=True))
    return course_ids


def student_has_course_access(student, course):
    if not student or not course:
        return False
    return PlanSubscription.objects.filter(
        student=student,
        courses=course,
        payment_status__in=[
            PlanSubscription.PAYMENT_PAID,
            PlanSubscription.PAYMENT_MANUAL,
        ],
        plan__is_active=True,
    ).distinct().select_related("plan").filter(
        id__in=[
            subscription.id
            for subscription in PlanSubscription.objects.filter(
                student=student,
                courses=course,
                payment_status__in=[
                    PlanSubscription.PAYMENT_PAID,
                    PlanSubscription.PAYMENT_MANUAL,
                ],
                plan__is_active=True,
            ).select_related("plan")
            if subscription.has_access_now
        ]
    ).exists()


def user_has_course_access(user, course):
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    return student_has_course_access(get_student_from_user(user), course)
