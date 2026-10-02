-- KEYS[1]=retained version watermark; KEYS[2]=expiring cached snapshot.
-- Lab versions fit exactly in Lua numbers. Do not use this for BIGINT > 2^53-1.
local incoming = tonumber(ARGV[1])
local floor = tonumber(redis.call('GET', KEYS[1]) or '0')
if incoming < floor then return 0 end
redis.call('SET', KEYS[1], tostring(incoming))
redis.call('SET', KEYS[2], ARGV[2], 'PX', ARGV[3])
return 1
