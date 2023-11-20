from app import scheduler
import os


while len(scheduler.get_jobs()) > 0:
    scheduler.remove_job(scheduler.get_jobs()[0].id)

os.system("killall gunicorn")
