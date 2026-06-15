from django.urls import path

from . import views

app_name = "course"

urlpatterns = [
    path("", views.CourseListView.as_view(), name="course-list"),
    path("my/", views.MyAccessibleCoursesView.as_view(), name="my-accessible-courses"),
    path("<int:pk>/", views.CourseDetailView.as_view(), name="course-detail"),
    path("<int:course_id>/exams/", views.CourseExamListView.as_view(), name="course-exams"),
]
