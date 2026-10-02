-- Acknowledging this script establishes the watermark in this Redis instance.
local incoming = tonumber(ARGV[1])
local floor = tonumber(redis.call('GET', KEYS[1]) or '0')
if incoming < floor then return 0 end
redis.call('SET', KEYS[1], tostring(incoming))
redis.call('DEL', KEYS[2])
return 1
