import { Router } from "express";
import { userControllers } from "./user.controller";
import auth from "../../middlewares/checkAuth";
import validateRequest from "../../middlewares/validateRequest";
import { userValidation } from "./user.validation";

const router = Router();

router.get("/me", auth("System_Admin", "Business_Admin"), userControllers.getMyProfile);
router.patch(
    "/me",
    auth("System_Admin", "Business_Admin"),
    validateRequest(userValidation.updateProfileZodSchema),
    userControllers.updateMyProfile
);

export const userRouter = router;