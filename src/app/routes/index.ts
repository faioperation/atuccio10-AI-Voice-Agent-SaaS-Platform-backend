import { Router } from "express";
import { authRouter } from "../modules/auth/auth.route";


export const rootRouter = Router();

const moduleRoutes = [
  {
    path: "/auth",
    element: authRouter,
  }
];

moduleRoutes.forEach((x) => rootRouter.use(x.path, x.element));