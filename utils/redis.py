class Redis:


    async def update(sorted_set:str,transporter_id:str,rate:float) -> (any,str):
        pass

    async def get_first(sorted_set:str):
        pass

    async def get_last(sorted_set:str):
        pass

    async def get_first_n(sorted_set : str, n : int):
        pass

    async def get_last_n(sorted_set : str, n : int):
        pass

    async def exists(sorted_set : str) -> bool:
        pass