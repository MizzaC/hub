# Mizzac project
When you install for the first time this project:

Install all packages needed for the project:

    pip install -r requirements.txt

For all “python manage.py” commands, please go to hub/Mizzac/ directory

    cd Mizzac

Update your database for a first Django utilization:

    python manage.py makemigrations
    python manage.py migrate

Initialize database with default values (Optional but recommended)

    python manage.py loaddata ToolBoard/fixtures/tools.json
    python manage.py loaddata DrunkBoard/fixtures/aromes.json
    python manage.py loaddata DrunkBoard/fixtures/couleurs.json

To create a superuser to connect to applications as such, particularly for test purposes (Optional)

    python manage.py createsuperuser --username <username> --email <mail>

To start the server locally

    python manage.py runserver


Learn more about Django:
    Documentation for first steps in Django:
        https://docs.djangoproject.com/fr/4.2/intro/
    All Documentations about Django:
        https://docs.djangoproject.com/en/4.2/contents/

Learn more about Git
    Cheat Sheet Git Commands:
        https://git-scm.com/docs
    All Documentation about Git:
        https://docs.github.com/get-started
