"""
Django Admin configuration for importing dummy data via JSON upload.
"""
import json
from django import forms
from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import render
from django.db import transaction

from core.management.commands.import_dummy_data import Command as ImportDummyDataCommand


class DummyDataImportForm(forms.Form):
    json_file = forms.FileField(
        label='JSON File',
        help_text='Upload a JSON file with dummy data',
        required=True,
        widget=forms.ClearableFileInput(attrs={'accept': '.json'})
    )
    clear_existing = forms.BooleanField(
        label='Clear existing dummy data first',
        required=False,
        initial=False
    )


def import_dummy_data_view(request):
    """
    Admin view to upload and import dummy data from JSON file.
    Access: Superuser only
    URL: /admin/import-dummy-data/
    """
    if not request.user.is_superuser:
        messages.error(request, 'Only superusers can import dummy data.')
        return render(request, 'admin/import_dummy_data.html', {
            'title': 'Import Dummy Data'
        })

    if request.method == 'POST':
        form = DummyDataImportForm(request.POST, request.FILES)
        if form.is_valid():
            json_file = form.cleaned_data['json_file']
            clear_existing = form.cleaned_data.get('clear_existing', False)

            try:
                data = json.loads(json_file.read().decode('utf-8'))

                cmd = ImportDummyDataCommand()

                if clear_existing:
                    messages.info(request, 'Clearing existing dummy data...')
                    cmd.clear_data()

                admin_data = data.get('admin', {})
                students_data = data.get('students', [])
                categories_data = data.get('question_categories', [])
                courses_data = data.get('courses', [])
                questions_data = data.get('questions', [])
                exams_data = data.get('exams', [])
                plans_data = data.get('plans', [])
                subscriptions_data = data.get('subscriptions', [])

                with transaction.atomic():
                    cmd.create_admin(admin_data)
                    students = cmd.create_students(students_data)
                    categories = cmd.create_categories(categories_data)
                    courses = cmd.create_courses(courses_data)
                    questions = cmd.create_questions(questions_data, courses, categories)
                    exams = cmd.create_exams(exams_data, courses, questions)
                    plans = cmd.create_plans(plans_data)
                    subscriptions = cmd.create_subscriptions(subscriptions_data, students, plans, courses)

                msg = (
                    f"Dummy data imported successfully! "
                    f"Admin: {admin_data.get('username', 'N/A')}, "
                    f"Students: {len(students_data)}, "
                    f"Courses: {len(courses_data)}, "
                    f"Questions: {len(questions_data)}, "
                    f"Exams: {len(exams_data)}, "
                    f"Plans: {len(plans_data)}, "
                    f"Subscriptions: {len(subscriptions_data)}"
                )
                messages.success(request, msg)

            except json.JSONDecodeError as e:
                messages.error(request, f'Invalid JSON file: {str(e)}')
            except Exception as e:
                messages.error(request, f'Error importing data: {str(e)}')
        else:
            messages.error(request, 'Please select a valid JSON file.')

    form = DummyDataImportForm()
    return render(request, 'admin/import_dummy_data.html', {
        'title': 'Import Dummy Data',
        'form': form
    })


class DummyDataAdminSite(admin.AdminSite):
    final_catch_all_view = False

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-dummy-data/', self.admin_view(import_dummy_data_view), name='import_dummy_data'),
        ]
        return custom_urls + urls


admin_site = DummyDataAdminSite(name='dummy_data_admin')
