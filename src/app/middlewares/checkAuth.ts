import { NextFunction, Request, Response } from "express"
import httpStatus from "http-status"
import ApiError from "../errors/ApiError";
import config from "../config";
import { verifyToken } from "../utils/jwt";


const auth = (...roles: string[]) => {
    return async (req: Request & { user?: any }, res: Response, next: NextFunction) => {
        try {
              const token =
                req.cookies?.accessToken ||
                req.headers?.authorization?.split(" ")[1];

            if (!token) {
                throw new ApiError(httpStatus.UNAUTHORIZED, "You are not authorized!")
            }

            const verifyUser = verifyToken(token, config.JWT_ACCESS_TOKEN as string);

            req.user = verifyUser;

            if (roles.length && !roles.includes(verifyUser.role)) {
                throw new ApiError(httpStatus.UNAUTHORIZED, "You are not authorized!")
            }

            next();
        }
        catch (err) {
            next(err)
        }
    }
}

export default auth;