import { z } from "zod";

const loginZodSchema = z.object({
    body: z.object({
        email: z.string({ message: "Email is required" }).email("Invalid email"),
        password: z.string({ message: "Password is required" }),
    }),
});

const registerUserZodSchema = z.object({
    body: z.object({
        name: z.string({ message: "Name is required" }),
        email: z.string({ message: "Email is required" }).email("Invalid email"),
        password: z.string({ message: "Password is required" }).min(6, "Password must be at least 6 characters"),
        contactNo: z.string({ message: "Contact number is required" }),
        role: z.enum(["System_Admin", "Business_Admin"]).optional(),
    }),
});

const changePasswordZodSchema = z.object({
    body: z.object({
        email: z.string({ message: "Email is required" }).email("Invalid email"),
        newPassword: z.string({ message: "New password is required" }).min(6, "Password must be at least 6 characters"),
    }),
});

const forgotPasswordZodSchema = z.object({
    body: z.object({
        email: z.string({ message: "Email is required" }).email("Invalid email"),
    }),
});

const verifyOtpZodSchema = z.object({
    body: z.object({
        email: z.string({ message: "Email is required" }).email("Invalid email"),
        otp: z.string({ message: "OTP is required" }),
    }),
});

export const authValidation = {
    loginZodSchema,
    registerUserZodSchema,
    changePasswordZodSchema,
    forgotPasswordZodSchema,
    verifyOtpZodSchema,
};