import httpStatus from "http-status";
import ApiError from "../../errors/ApiError";
import { prisma } from "../../db_connection/prisma";

const db = prisma as any;

// Get My Profile
const getMyProfile = async (userId: string) => {
    const user = await db.user.findUnique({
        where: { id: userId },
        select: {
            id: true,
            name: true,
            email: true,
            role: true,
            contactNo: true,
            photo: true,
            address: true,
            isBlocked: true,
            createdAt: true,
            updatedAt: true,
        },
    });

    if (!user) {
        throw new ApiError(httpStatus.NOT_FOUND, "User not found");
    }

    return user;
};

// Update My Profile
const updateMyProfile = async (
    userId: string,
    payload: { name?: string; contactNo?: string; photo?: string; address?: string }
) => {
    const user = await db.user.findUnique({
        where: { id: userId },
    });

    if (!user) {
        throw new ApiError(httpStatus.NOT_FOUND, "User not found");
    }

    const updatedUser = await db.user.update({
        where: { id: userId },
        data: payload,
        select: {
            id: true,
            name: true,
            email: true,
            contactNo: true,
            photo: true,
            address: true,
            updatedAt: true,
        },
    });

    return updatedUser;
};

export const userServices = {
    getMyProfile,
    updateMyProfile,
};