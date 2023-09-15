from config.redis import r as redis
from utils.utilities import log


class Redis:

    async def update(self, sorted_set: str, transporter_id: str, transporter_name: str, comment: str, rate: float, attempts: int) -> (any, str):

        log("TRANSPORTER ID",transporter_id)
        log("TRANSPORTER NAME",transporter_name)
        log("COMMENT",comment)
        log("RATE",rate)
        log("NUMBER OF ATTEMPTS",attempts)

        redis.hmset(transporter_id, {
            'transporter_id': transporter_id,
            'transporter_name': transporter_name,
            'comment': comment,
            'attempts': attempts
        })
        
        log("HASHING IN REDIS","OK")

        redis.zadd(sorted_set, {transporter_id: rate})
        
        log("SORTED SET APPEND IN REDIS","OK")
        
        transporter_data_with_rates = []

        transporter_ids = await self.get_all(sorted_set=sorted_set)
        
        log("TRANSPORTER IDS",transporter_ids)

        for transporter_id in transporter_ids:
            rate = redis.zscore(sorted_set, transporter_id)
            log("TRANSPORTER DETAILS",{"TRANSPORTER_ID" : transporter_id, "RATE":rate})
            transporter_data = redis.hgetall(transporter_id)
            
            log("TRANSPORTER DETAILS BEFORE RATE",transporter_data)

            transporter_data['rate'] = rate
            log("TRANSPORTER DETAILS AFTER RATE",transporter_data)
            
            
            

            transporter_data_with_rates.append(transporter_data)
        
        log("LIVE BID RESULTS",transporter_data_with_rates)

        return (transporter_data_with_rates,"")


    async def get_first(self, sorted_set: str):
        return redis.zrange(sorted_set, 0, 0)

    async def get_last(self, sorted_set: str):
        return redis.zrevrange(sorted_set, 0, 0)

    async def get_first_n(self, sorted_set: str, n: int):
        return redis.zrange(sorted_set, 0, n)

    async def get_last_n(self, sorted_set: str, n: int):
        return redis.zrevrange(sorted_set, 0, n)

    async def get_all(self, sorted_set: str):
        log("ALL RECORDS IN SORTED SET")
        return redis.zrange(sorted_set, 0, -1)

    async def exists(self, sorted_set: str, key: str) -> bool:

        if not redis.zscore(sorted_set, key):
            return False
        return True
