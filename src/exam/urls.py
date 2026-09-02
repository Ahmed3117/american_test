from django.urls import path
from . import views

app_name = 'exam'

urlpatterns = [
    path('', views.StudentExamListCreateView.as_view(), name='exam-list-create'),
    path('config/', views.ExamConfigStatusView.as_view(), name='exam-config-status'),
    path('question-categories/', views.StudentQuestionCategoryOptionListView.as_view(), name='question-category-options'),
    path('units/', views.StudentUnitOptionListView.as_view(), name='unit-options'),
    path('years/', views.StudentYearOptionListView.as_view(), name='year-options'),
    path('<int:pk>/', views.StudentExamDetailView.as_view(), name='exam-detail'),
    path('<int:exam_id>/check_my_ability_to_start/', views.CheckExamStartAbility.as_view(), name='check-exam-start-ability'),
    path('<int:exam_id>/start/', views.StartExam.as_view(), name='start-exam'),
    path('<int:exam_id>/submit/', views.SubmitExam.as_view(), name='submit-exam'),
    path('exam-results/', views.StudentExamResultsView.as_view(), name='student-exam-results'),
    path('<int:exam_id>/result/', views.GetMyExamResult.as_view(), name='get-my-exam-result'),
    path('<int:exam_id>/result/<int:result_trial_id>/', views.GetMyExamResultForTrial.as_view(), name='get-my-exam-result-for-trial'),
    #^ ------- Student Temp Exams ------- ^#
    path('student-bank/', views.StudentBankListView.as_view(), name='student-bank-list'),
    path('create-temp-exam/', views.CreateTempExam.as_view(), name='create-temp-exam'),
    path('submit-temp-exam-results/', views.SubmitTempExamResults.as_view(), name='submit-temp-exam-results'),

    #^ ------- Student Created Exams ------- ^#
    path('create-student-exam/', views.CreateStudentExam.as_view(), name='create-student-exam'),
    path('submit-student-exam-results/', views.SubmitStudentExamResults.as_view(), name='submit-student-exam-results'),
    path('student-created-exams/', views.StudentCreatedExamListView.as_view(), name='student-created-exams'),
    
    #^ ------- Admin Question Bank ------- ^#
    path('admin-question-bank/', views.AdminQuestionBankListView.as_view(), name='admin-question-bank'),

]


