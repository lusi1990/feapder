from feapder.db.redisdb import RedisDB
import time
db = RedisDB.from_url("redis://10.206.77.130:6379/6")

# db.clear("test")
db.zincrby("test", 1.0, "a")
