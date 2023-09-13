from apscheduler.schedulers.background import BackgroundScheduler

from utils.bids.biddingDeprecated import Bid

bid = Bid()

def schedule_jobs():
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=bid.initiate_bid,trigger="interval",id="background-job-1",minutes=1)
    scheduler.add_job(func=bid.close_bid,trigger="interval",id="background-job-2",minutes=1)
    scheduler.start()