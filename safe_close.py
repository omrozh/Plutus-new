from app import scheduler
import os

for i in scheduler.get_jobs():
    scheduler.remove_job(i.id)

os.system("gunicorn -w 3 app:app")
