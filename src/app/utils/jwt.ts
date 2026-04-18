import jwt, { JwtPayload, SignOptions } from "jsonwebtoken";

export type TJwtPayload = {
  id: string;
  email: string;
  name: string;
  role: string;
};

export const generateToken = (
  payload: TJwtPayload,
  secret: string,
  expiresIn: string,
) => {
  const token = jwt.sign(payload, secret, {
    expiresIn,
  } as SignOptions);
  return token;
};

export const verifyToken = (token: string, secret: string): JwtPayload => {
  const verifiedToken = jwt.verify(token, secret) as JwtPayload;
  return verifiedToken;
};