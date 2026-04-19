import { Router } from "express";
import { authControllers } from "./auth.controller";
import auth from "../../middlewares/checkAuth";
import validateRequest from "../../middlewares/validateRequest";
import { authValidation } from "./auth.validation";

const router = Router()

router.post("/login", validateRequest(authValidation.loginZodSchema), authControllers.userLogin)
router.post("/register", validateRequest(authValidation.registerUserZodSchema), authControllers.registerUser)
router.post("/logout", authControllers.userLogout)
router.post("/forgot-password", validateRequest(authValidation.forgotPasswordZodSchema), authControllers.userForgotPassword)
router.post("/verify-otp", validateRequest(authValidation.verifyOtpZodSchema), authControllers.userVerifyOTP)
router.post("/change-password", validateRequest(authValidation.changePasswordZodSchema), authControllers.userChangePassword)

export const authRouter = router;