from config.redis import redis

class Redis:


    async def update(self,sorted_set:str,transporter_id:str,rate:float) -> (any,str):
        if self.exists(sorted_set=sorted_set,key=transporter_id):
            redis.zadd(sorted_set,{transporter_id : rate},xx=True)
        
        redis.zadd(sorted_set,{transporter_id : rate})

    async def get_first(self,sorted_set:str):
        pass

    async def get_last(self,sorted_set:str):
        pass

    async def get_first_n(self,sorted_set : str, n : int):
        pass

    async def get_last_n(self,sorted_set : str, n : int):
        pass

    async def exists(self,sorted_set : str,key : str) -> bool:
        if not redis.zscore(sorted_set, key):
            return False
        return True

        