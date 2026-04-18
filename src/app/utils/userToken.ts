import config from "../config";
import { generateToken, TJwtPayload } from "./jwt";

export const createUserToken = (payload: Partial<TJwtPayload>) => {
  const data: TJwtPayload = {
    id: payload.id!,
    email: payload.email!,
    name: payload.name!,
    role: payload.role!,
  };

  const accessToken = generateToken(
    data,
    config.JWT_ACCESS_TOKEN as string,
    config.JWT_ACCESS_EXPIRES as string,
  );
  const refreshToken = generateToken(
    data,
    config.JWT_REFRESH_TOKEN as string,
    config.JWT_REFRESH_EXPIRES as string,
  );

  return { accessToken, refreshToken };
};