import { createClient } from 'redis';
import config from '.';


export const redisClient = createClient({
    username: config.RedisUserName,
    password: config.RedisPassword,
    socket: {
        host: config.RedisHost,
        port: Number(config.RedisPort)
    }
});

redisClient.on('error', err => console.log('Redis Client Error', err));

export const connectRedis = async () => {
    if (!redisClient.isOpen) {
        await redisClient.connect();
        console.log("Redis Connected");
    }
}