#!/bin/bash
set -o errexit

pip install -r requirements.txt

python manage.py migrate
python manage.py collectstatic --no-input

# Create admin user with role='admin'
python manage.py shell <<EOF
from accounts.models import User
if not User.objects.filter(username='admin').exists():
    admin = User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='admin123',
        role='admin',
        first_name='System',
        last_name='Admin'
    )
    print("Admin user created: admin / admin123 (role=admin)")
else:
    admin = User.objects.get(username='admin')
    if admin.role != 'admin':
        admin.role = 'admin'
        admin.save()
        print("Existing admin updated to role=admin")
    else:
        print("Admin user already exists with correct role")
EOF
