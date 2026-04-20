import { z } from "zod";

const updateProfileZodSchema = z.object({
    body: z.object({
        name: z.string().optional(),
        contactNo: z.string().optional(),
        photo: z.string().optional(),
        address: z.string().optional(),
    }),
});

export const userValidation = {
    updateProfileZodSchema,
};