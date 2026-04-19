import express, { Application, Request, Response } from "express";
import cors from "cors";
const app:Application = express();
import cookieParser from "cookie-parser";
import globalErrorHandler from "./app/middlewares/globalErrorHandler";
import notFound from "./app/middlewares/notFound";
import { rootRouter } from "./app/routes";

// Middleware
app.use(cors());
app.use(express.json());
app.use(cookieParser());

app.get("/", (req: Request, res: Response) => {
  res.status(200).json({
    message: "CLINCH Server is running successfully",
    upTime: process.uptime().toFixed(2) + " sec",
    Date: new Date(),
  });
});

app.use("/api/v1",rootRouter)


app.use(globalErrorHandler)
app.use(notFound)
export default app;