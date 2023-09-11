from apscheduler.schedulers.background import BackgroundScheduler

from utils.bids.bidding import initiate_bid,close_bid


def schedule_jobs():
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=initiate_bid,trigger="interval",id="background-job-1",minutes=1)
    scheduler.add_job(func=close_bid,trigger="interval",id="background-job-2",minutes=1)
    scheduler.start()