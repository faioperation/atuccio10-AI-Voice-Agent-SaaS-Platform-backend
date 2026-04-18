import { Response } from "express";
import config from "../config";


type TToken = {
  accessToken: string;
  refreshToken: string;
};

export const setCookie = (res: Response, token: TToken) => {
  const isProduction = config.NODE_ENV === "production";

  const cookieOptions = {
    httpOnly: true,
    secure: isProduction,           // false in dev/HTTP, true in prod/HTTPS
    sameSite: isProduction ? ("none" as const) : ("lax" as const),
  };

  if (token.accessToken) {
    res.cookie("accessToken", token.accessToken, cookieOptions);
  }
  if (token.refreshToken) {
    res.cookie("refreshToken", token.refreshToken, cookieOptions);
  }
};