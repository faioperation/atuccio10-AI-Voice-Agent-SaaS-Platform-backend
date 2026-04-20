import { Router } from "express";
import { authRouter } from "../modules/auth/auth.route";
import { userRouter } from "../modules/user/user.routes";


export const rootRouter = Router();

const moduleRoutes = [
  {
    path: "/auth",
    element: authRouter,
  },
  {
    path: "/user",
    element: userRouter,
  }
];

moduleRoutes.forEach((x) => rootRouter.use(x.path, x.element));