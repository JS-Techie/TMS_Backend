from apscheduler.schedulers.background import BackgroundScheduler

class Scheduler:

    def new_scheduler(self):
        scheduler = BackgroundScheduler()
        return scheduler
    
    def start(self,scheduler):
        scheduler.start()