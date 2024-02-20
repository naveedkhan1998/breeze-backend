# This file contains the WSGI configuration required to serve up your
# web application at http://dtemplarsarsh.pythonanywhere.com/
# It works by setting the variable 'application' to a WSGI handler of some
# description.
#
# The below has been auto-generated for your Django project

import os
import sys

# add your project directory to the sys.path
project_home = '/home/dtemplarsarsh/breeze-backend'
sys.path.append('/home/dtemplarsarsh/breeze-backend')
sys.path.append('/home/dtemplarsarsh/breeze-backend/venv/lib/python3.10/site-packages')

# set environment variable to tell django where your settings.py is
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')


# serve django via WSGI
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

