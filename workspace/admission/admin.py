from django.contrib import admin
from .models import User, Application, Program, Department

admin.site.register(User)
admin.site.register(Application)
admin.site.register(Program)
admin.site.register(Department)
