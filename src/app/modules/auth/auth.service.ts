import bcrypt from "bcrypt";
import httpStatus from "http-status";
import ApiError from "../../errors/ApiError";
import { sendEmail } from "../../utils/sendEmail";
import crypto from "crypto";

import { prisma } from "../../db_connection/prisma";
import { redisClient } from "../../config/redisConfig";

const db = prisma as any;

// Login
const loginUser = async (payload: { email: string; password: string }) => {
  const { email, password } = payload;

  const user = await db.user.findUnique({
    where: { email },
  });
  if (!user) {
    throw new ApiError(httpStatus.NOT_FOUND, "User not found");
  }
  if (user.isBlocked) {
    throw new ApiError(httpStatus.FORBIDDEN, "User is blocked");
  }

  const isMatch = await bcrypt.compare(password, user.password);
  if (!isMatch) {
    throw new ApiError(httpStatus.UNAUTHORIZED, "Invalid credentials");
  }

  return user;
};

// Register User (Admin creates users)
const registerUser = async (payload: {
  name: string;
  email: string;
  password: string;
  contactNo: string;
  role?: string;
}) => {
  const existingUser = await db.user.findUnique({
    where: { email: payload.email },
    select: { id: true },
  });
  if (existingUser) {
    throw new ApiError(httpStatus.CONFLICT, "Email already exists");
  }

  const hashed = await bcrypt.hash(payload.password, 8);

  const user = await db.user.create({
    data: {
      name: payload.name,
      email: payload.email,
      password: hashed,
      contactNo: payload.contactNo,
      role: payload.role || "User",
    },
    select: {
      id: true,
      name: true,
      email: true,
      role: true,
      createdAt: true,
    },
  });

  return user;
};

// Forget Password
const generateOtp = (length = 6) => {
  const otp = crypto.randomInt(10 ** (length - 1), 10 ** length).toString();
  return otp;
};

const forgotPassword_sendPassword = async (email: string) => {
  const isUserExist = await db.user.findUnique({
    where: { email: email },
  });

  if (!isUserExist) {
    throw new ApiError(httpStatus.BAD_REQUEST, "User does not exist");
  }

  const otp = generateOtp();
  const redisKey = `otp:${email}`;

  await redisClient.set(redisKey, otp, {
    expiration: {
      type: "EX",
      value: 2 * 60,
    },
  });

  await sendEmail({
    to: email,
    subject: "Your OTP Code",
    tempName: "otp",
    tempData: {
      name: isUserExist.name,
      otp: otp,
    },
  });
};

const verifyOTP = async (email: string, otp: string) => {
  const user = await db.user.findUnique({
    where: { email: email },
  });

  if (!user) {
    throw new ApiError(404, "User not found");
  }

  const redisKey = `otp:${email}`;
  const savedOtp = await redisClient.get(redisKey);

  if (!savedOtp) {
    throw new ApiError(401, "Invalid OTP");
  }

  if (savedOtp !== otp) {
    throw new ApiError(401, "Invalid OTP");
  }

  return { isOTPValid: true };
};

const changePassword = async (newPassword: string, email: string) => {
  const user = await db.user.findUnique({
    where: { email },
  });

  if (!user) {
    throw new ApiError(httpStatus.NOT_FOUND, "User not found");
  }

  if (!newPassword) {
    throw new ApiError(httpStatus.UNAUTHORIZED, "New password is not found");
  }

  const hashedPassword = await bcrypt.hash(newPassword, 10);

  await db.user.update({
    where: { email },
    data: {
      password: hashedPassword,
    },
  });

  return {
    success: true,
    message: "Password changed successfully",
  };
};

export const authServices = {
  loginUser,
  registerUser,
  forgotPassword_sendPassword,
  verifyOTP,
  changePassword,
};