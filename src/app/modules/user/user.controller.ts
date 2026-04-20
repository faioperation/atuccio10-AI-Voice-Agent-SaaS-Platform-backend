import { catchAsync } from "../../utils/catchAsync";
import { sendResponse } from "../../utils/sendResponse";
import { userServices } from "./user.service";

const getMyProfile = catchAsync(async (req: any, res, next) => {
    const userId = req.user.id;
    console.log(req.user.id)
    const user = await userServices.getMyProfile(userId);
    sendResponse(res, {
        success: true,
        message: "Profile fetched successfully",
        statusCode: 200,
        data: user,
    });
});

const updateMyProfile = catchAsync(async (req: any, res, next) => {
    const userId = req.user.id;
    const user = await userServices.updateMyProfile(userId, req.body);
    sendResponse(res, {
        success: true,
        message: "Profile updated successfully",
        statusCode: 200,
        data: user,
    });
});

export const userControllers = {
    getMyProfile,
    updateMyProfile,
};