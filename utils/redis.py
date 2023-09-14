from config.redis import r as redis


class Redis:

    async def update(self, sorted_set: str, transporter_id: str, transporter_name: str, comment: str, rate: float, attempts: int) -> (any, str):


        redis.hmset(transporter_id, {
            'transporter_id': transporter_id,
            'transporter_name': transporter_name,
            'comment': comment,
            'attempts': attempts
        })

        redis.zadd(sorted_set, {transporter_id: rate})
        transporter_data_with_rates = []

        transporter_ids = self.get_all(sorted_set=sorted_set)

        for transporter_id in transporter_ids:
            rate = redis.zscore(sorted_set, transporter_id)
            transporter_data = redis.hgetall(transporter_id)

            transporter_data['rate'] = rate

            transporter_data_with_rates.append(transporter_data)

        return transporter_data_with_rates


    async def get_first(self, sorted_set: str):
        return redis.zrange(sorted_set, 0, 0)

    async def get_last(self, sorted_set: str):
        return redis.zrevrange(sorted_set, 0, 0)

    async def get_first_n(self, sorted_set: str, n: int):
        return redis.zrange(sorted_set, 0, n)

    async def get_last_n(self, sorted_set: str, n: int):
        return redis.zrevrange(sorted_set, 0, n)

    async def get_all(self, sorted_set: str):
        return redis.zrange(sorted_set, 0, -1)

    async def exists(self, sorted_set: str, key: str) -> bool:

        if not redis.zscore(sorted_set, key):
            return False
        return True
