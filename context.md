# CLINCH Backend — Full Project Context

> **Purpose:** This document is a single source of truth for the `clinch-backend` codebase.
> It is designed to be fed to an MCP (Model Context Protocol) server so that an AI assistant
> can understand the entire project in one read and implement new features correctly, consistently,
> and without needing to re-read the source files.

---

## 1. Project Overview

| Field | Value |
|---|---|
| **Project Name** | clinch-backend |
| **Language** | TypeScript (strict mode) |
| **Runtime** | Node.js (CommonJS modules) |
| **Framework** | Express.js v5 |
| **ORM** | Prisma v7 (PostgreSQL via `@prisma/adapter-pg`) |
| **Database** | PostgreSQL |
| **Cache / Session Store** | Redis (Redis Cloud) |
| **Auth** | JWT (access + refresh tokens) stored as HTTP-only cookies |
| **Email** | Nodemailer + SMTP (Gmail) + EJS templates |
| **Validation** | Zod v4 |
| **Password Hashing** | bcrypt |
| **Dev Server** | `ts-node-dev --respawn --transpile-only` |
| **Local Port** | 5000 |
| **API Base URL** | `/api/v1` |

---

## 2. Directory Structure

```
clinch-backend/
├── prisma/
│   ├── schema.prisma          # Generator + datasource config
│   ├── userSchema.prisma      # User model + ERole enum (merged manually)
│   └── migrations/
│       └── 20260418212218_project_init/   # Initial migration
├── generated/
│   └── prisma/                # Prisma Client output directory (auto-generated)
├── src/
│   ├── app.ts                 # Express app setup, global middleware, routes mount
│   ├── server.ts              # HTTP server bootstrap, Redis connect, process signals
│   └── app/
│       ├── config/
│       │   ├── index.ts       # All env vars exported as a config object
│       │   └── redisConfig.ts # Redis client creation + connectRedis()
│       ├── db_connection/
│       │   └── prisma.ts      # Prisma client singleton (using PrismaPg adapter)
│       ├── errors/
│       │   └── ApiError.ts    # Custom error class with statusCode
│       ├── middlewares/
│       │   ├── checkAuth.ts       # JWT auth guard — extracts token from cookie or Bearer header
│       │   ├── globalErrorHandler.ts  # Express error handler (Prisma + ApiError aware)
│       │   ├── notFound.ts        # 404 handler
│       │   └── validateRequest.ts # Zod schema request validator
│       ├── modules/
│       │   └── auth/
│       │       ├── auth.controller.ts  # Route handler functions
│       │       ├── auth.route.ts       # Express router
│       │       ├── auth.service.ts     # Business logic
│       │       └── auth.validation.ts  # Zod schemas
│       ├── routes/
│       │   └── index.ts       # Root router — assembles all module routers
│       └── utils/
│           ├── catchAsync.ts  # Async error wrapper for route handlers
│           ├── jwt.ts         # generateToken() + verifyToken()
│           ├── QueryBuilder.ts # Fluent Prisma query builder (filter/search/sort/paginate)
│           ├── sendEmail.ts   # Nodemailer + EJS email sender
│           ├── sendResponse.ts # Standardized JSON response helper
│           ├── setCookie.ts   # Sets accessToken + refreshToken cookies
│           └── userToken.ts   # createUserToken() — generates access + refresh JWTs
├── .env                       # Environment variables (never commit secrets)
├── package.json
├── prisma.config.ts           # Prisma CLI config (schema path, migrations path, datasource)
└── tsconfig.json
```

---

## 3. Environment Variables (`.env`)

All env vars are consumed through `src/app/config/index.ts`. Never access `process.env` directly — always import `config`.

| Variable | Description |
|---|---|
| `PORT` | Server port (default: 5000) |
| `DATABASE_URL` | PostgreSQL connection string |
| `NODE_ENV` | `production` or `development` |
| `BCRYPT_SALT` | bcrypt salt rounds |
| `JWT_ACCESS_TOKEN` | JWT access token secret |
| `JWT_ACCESS_EXPIRES` | JWT access token expiry (e.g., `1d`) |
| `JWT_REFRESH_TOKEN` | JWT refresh token secret |
| `JWT_REFRESH_EXPIRES` | JWT refresh token expiry (e.g., `30d`) |
| `SMTP_HOST` | SMTP host (smtp.gmail.com) |
| `SMTP_PORT` | SMTP port (465) |
| `SMTP_USER` | SMTP login email |
| `SMTP_FROM` | Sender email address |
| `SMTP_PASS` | Gmail app password |
| `FRONTEND_URL` | Frontend origin (for CORS / email links) |
| `RedisUserName` | Redis username (usually `default`) |
| `RedisPassword` | Redis password |
| `RedisHost` | Redis host |
| `RedisPort` | Redis port |
| `APIFY_TOKEN` | Apify API token (for future scraping features) |

---

## 4. Database Schema

### `schema.prisma` (generator + datasource)
```prisma
generator client {
  provider = "prisma-client-js"
  output   = "../generated/prisma"
}

datasource db {
  provider = "postgresql"
}
```
> The `url` is NOT in `schema.prisma`. It is passed at runtime via the `PrismaPg` adapter
> using `process.env.DATABASE_URL`.

### `userSchema.prisma` (User model)
```prisma
model User {
    id         String     @id @default(uuid())
    name       String
    email      String     @unique
    role       ERole      @default(User)
    password   String
    contactNo  String
    photo      String?
    address    String?
    createdAt  DateTime   @default(now())
    updatedAt  DateTime   @updatedAt
    isBlocked  Boolean    @default(false)
}

enum ERole {
    Admin
    User
}
```

> **Schema split convention:** Each domain model lives in its own `.prisma` file (e.g., `userSchema.prisma`).
> These are manually referenced/merged. When adding a new model, create a `<domain>Schema.prisma` file.

---

## 5. Architecture Pattern — Module-Based MVC

Every feature domain lives under `src/app/modules/<moduleName>/` with exactly 4 files:

```
<moduleName>/
├── <moduleName>.controller.ts   # Thin: calls service, calls sendResponse()
├── <moduleName>.route.ts        # Express Router: applies middleware + maps controller
├── <moduleName>.service.ts      # All business logic + DB calls via Prisma
└── <moduleName>.validation.ts   # Zod schemas (one per endpoint)
```

**Register new modules** in `src/app/routes/index.ts`:
```typescript
const moduleRoutes = [
  { path: "/auth",       element: authRouter },
  { path: "/users",      element: usersRouter },   // <-- add new modules here
];
moduleRoutes.forEach((x) => rootRouter.use(x.path, x.element));
```

---

## 6. Core Files — Detailed Reference

### `src/app.ts` — Express Application
```typescript
// Middleware stack (in order):
app.use(cors());
app.use(express.json());
app.use(cookieParser());

// Health check
app.get("/")  // Returns { message, upTime, Date }

// All API routes
app.use("/api/v1", rootRouter);

// Error handling (MUST be last)
app.use(globalErrorHandler);
app.use(notFound);
```

### `src/server.ts` — Server Bootstrap
- Connects Redis → starts HTTP server
- Handles: `unhandledRejection`, `uncaughtException`, `SIGTERM`, `SIGINT`
- Graceful shutdown: closes server → disconnects Prisma → exits

### `src/app/db_connection/prisma.ts` — Prisma Singleton
```typescript
import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "../../../generated/prisma";

const adapter = new PrismaPg({ connectionString: process.env.DATABASE_URL });
const prisma = new PrismaClient({ adapter });
export { prisma };
```
> **Usage in services:** `import { prisma } from "../../db_connection/prisma";`
> The `db` alias is created as `const db = prisma as any;` in services to work around
> TypeScript strict typing issues with schema splits before the Prisma client is regenerated.

### `src/app/config/index.ts` — Config Object
```typescript
import dotenv from "dotenv";
import path from "path";
dotenv.config({ path: path.join(process.cwd(), ".env") });

export default {
  PORT, DATABASE, NODE_ENV,
  JWT_ACCESS_TOKEN, JWT_ACCESS_EXPIRES,
  JWT_REFRESH_TOKEN, JWT_REFRESH_EXPIRES,
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_FROM, SMTP_PASS,
  FRONTEND_URL,
  RedisUserName, RedisPassword, RedisHost, RedisPort,
  APIFY_TOKEN
};
```

### `src/app/config/redisConfig.ts` — Redis Client
```typescript
export const redisClient = createClient({
  username, password,
  socket: { host, port }
});

// Usage for OTP storage:
await redisClient.set(`otp:${email}`, otp, { expiration: { type: "EX", value: 120 } });
const saved = await redisClient.get(`otp:${email}`);
```

---

## 7. Utilities Reference

### `catchAsync.ts`
Wraps async route handlers — automatically forwards errors to `next()`.
```typescript
export const catchAsync = (fn: RequestHandler) => (req, res, next) => {
  Promise.resolve(fn(req, res, next)).catch((err) => next(err));
};
```
**Usage:** `const myController = catchAsync(async (req, res, next) => { ... });`

---

### `sendResponse.ts`
Standardized success response shape:
```typescript
sendResponse(res, {
  success: true,
  message: "...",
  statusCode: 200,
  data: result,       // T | T[] | null
  meta: {             // optional, for paginated lists
    page, limit, total, totalPage
  }
});
```
**Response shape:**
```json
{
  "success": true,
  "message": "...",
  "meta": null,
  "data": { ... }
}
```

---

### `ApiError.ts`
Custom error class — throw this from services for known HTTP errors:
```typescript
throw new ApiError(httpStatus.NOT_FOUND, "User not found");
throw new ApiError(httpStatus.CONFLICT, "Email already exists");
throw new ApiError(httpStatus.UNAUTHORIZED, "Invalid credentials");
throw new ApiError(httpStatus.FORBIDDEN, "User is blocked");
```

---

### `jwt.ts`
```typescript
// Payload shape:
type TJwtPayload = { id: string; email: string; name: string; role: string; };

generateToken(payload, secret, expiresIn)  // returns JWT string
verifyToken(token, secret)                 // returns JwtPayload
```

---

### `userToken.ts`
```typescript
// Creates BOTH access and refresh tokens for a user:
const { accessToken, refreshToken } = createUserToken(user);
// user must have: { id, email, name, role }
```

---

### `setCookie.ts`
```typescript
// Sets HTTP-only cookies with environment-aware security:
// - development: secure=false, sameSite="lax"
// - production:  secure=true,  sameSite="none"
setCookie(res, { accessToken, refreshToken });
```

---

### `sendEmail.ts`
Uses Nodemailer + EJS templates:
```typescript
await sendEmail({
  to: "user@example.com",
  subject: "Your OTP",
  tempName: "otp",          // maps to src/app/utils/templates/otp.ejs
  tempData: { name, otp },  // variables injected into EJS template
});
```
> **Template path:** `src/app/utils/templates/<tempName>.ejs`
> When adding new email types, create a corresponding `.ejs` file.

---

### `QueryBuilder.ts`
Fluent builder for Prisma queries with filtering, searching, sorting, and pagination.

```typescript
const qb = new QueryBuilder(req.query);

const { where, orderBy, skip, take } = qb
  .filter()         // exact-match filters (case-insensitive for strings)
  .search(["name", "email"])  // full-text OR search
  .sort("-createdAt")          // ?sort=-createdAt (desc), ?sort=name (asc)
  .paginate()       // ?page=1&limit=15
  .build();

const [data, total] = await Promise.all([
  db.user.findMany({ where, orderBy, skip, take }),
  db.user.count({ where }),
]);

const meta = qb.getMeta(total);
sendResponse(res, { ..., data, meta });
```

**Query param conventions:**
| Param | Description |
|---|---|
| `?searchTerm=` | Full-text search across configured fields |
| `?sort=-field` | Sort descending |
| `?sort=field` | Sort ascending |
| `?page=1` | Page number |
| `?limit=15` | Items per page |
| `?fields=name,email` | Only return specified fields |
| `?<field>=<value>` | Exact filter on any field |

---

## 8. Middleware Reference

### `checkAuth.ts` — JWT Authentication Guard
```typescript
// Usage syntaxes:
auth()                    // Any authenticated user
auth("Admin")             // Only admins
auth("Admin", "User")     // Admin or User

// Token extraction (in order):
// 1. req.cookies.accessToken
// 2. Authorization: Bearer <token>

// Attaches decoded payload to req.user:
// { id, email, name, role, iat, exp }
```

### `validateRequest.ts` — Zod Request Validator
```typescript
// Validates req.body against a Zod schema:
router.post("/login", validateRequest(authValidation.loginZodSchema), authControllers.userLogin);

// All Zod schemas use the wrapper pattern:
const schema = z.object({
  body: z.object({ ... })  // always wrap in { body: ... }
});
```

### `globalErrorHandler.ts` — Error Handler
Handles:
- `ApiError` → uses `err.statusCode` and `err.message`
- `Prisma.PrismaClientKnownRequestError` → handles P2002 (duplicate), P1000 (auth failed), P2003 (foreign key)
- `Prisma.PrismaClientValidationError` → 400
- `Prisma.PrismaClientUnknownRequestError` → 400
- `Prisma.PrismaClientInitializationError` → 400
- Any other error → 500

**Error response shape:**
```json
{
  "success": false,
  "message": "Error description",
  "error": { ... }
}
```

---

## 9. Auth Module — Full API Documentation

**Base path:** `/api/v1/auth`

### POST `/login`
- **Body:** `{ email: string, password: string }`
- **Response:** Sets `accessToken` + `refreshToken` cookies. Returns `{ data: { accessToken, refreshToken } }`
- **Errors:** 404 (not found), 403 (blocked), 401 (wrong password)

### POST `/register`
- **Body:** `{ name, email, password (min 6), contactNo, role?: "Admin"|"User" }`
- **Response:** 201, returns created user `{ id, name, email, role, createdAt }`
- **Note:** Currently open — no auth guard. Admin can use this to create users.

### POST `/logout`
- **Body:** None
- **Response:** Clears `accessToken` + `refreshToken` cookies. Returns 200.

### POST `/forgot-password`
- **Body:** `{ email: string }`
- **Flow:** Generates 6-digit OTP → stores in Redis with 2-minute TTL (`otp:<email>`) → sends OTP email via EJS template.
- **Response:** 200

### POST `/verify-otp`
- **Body:** `{ email: string, otp: string }`
- **Flow:** Looks up `otp:<email>` in Redis → compares OTP.
- **Response:** `{ isOTPValid: true }` or throws 401.

### POST `/change-password`
- **Body:** `{ email: string, newPassword: string (min 6) }`
- **Flow:** Finds user → hashes new password with bcrypt (10 rounds) → updates DB.
- **Response:** `{ success: true, message: "Password changed successfully" }`

---

## 10. How to Add a New Feature Module

Follow these steps **exactly** to maintain consistency:

### Step 1 — Create the Prisma schema file
```
prisma/<domain>Schema.prisma
```
Define the model. Then merge/import it into `schema.prisma` if needed, and run:
```bash
npx prisma migrate dev --name <migration_name>
npx prisma generate
```

### Step 2 — Create module files
```
src/app/modules/<domain>/
├── <domain>.controller.ts
├── <domain>.route.ts
├── <domain>.service.ts
└── <domain>.validation.ts
```

### Step 3 — Controller pattern (always use `catchAsync` + `sendResponse`)
```typescript
import { catchAsync } from "../../utils/catchAsync";
import { sendResponse } from "../../utils/sendResponse";
import { myService } from "./<domain>.service";

const createItem = catchAsync(async (req, res, next) => {
  const result = await myService.createItem(req.body);
  sendResponse(res, {
    success: true,
    message: "Item created successfully",
    statusCode: 201,
    data: result,
  });
});

export const myControllers = { createItem };
```

### Step 4 — Service pattern (always use `db = prisma as any`, throw `ApiError`)
```typescript
import { prisma } from "../../db_connection/prisma";
import ApiError from "../../errors/ApiError";
import httpStatus from "http-status";

const db = prisma as any;

const createItem = async (payload: {...}) => {
  // business logic here
  const item = await db.<model>.create({ data: payload });
  return item;
};

export const myService = { createItem };
```

### Step 5 — Validation pattern (wrap body in `z.object({ body: z.object({...}) })`)
```typescript
import { z } from "zod";

const createItemZodSchema = z.object({
  body: z.object({
    name: z.string({ message: "Name is required" }),
    // add fields
  }),
});

export const myValidation = { createItemZodSchema };
```

### Step 6 — Route pattern
```typescript
import { Router } from "express";
import auth from "../../middlewares/checkAuth";
import validateRequest from "../../middlewares/validateRequest";
import { myControllers } from "./<domain>.controller";
import { myValidation } from "./<domain>.validation";

const router = Router();

router.post("/", auth("Admin"), validateRequest(myValidation.createItemZodSchema), myControllers.createItem);
router.get("/", auth(), myControllers.getAll);

export const myRouter = router;
```

### Step 7 — Register in root router
```typescript
// src/app/routes/index.ts
import { myRouter } from "../modules/<domain>/<domain>.route";

const moduleRoutes = [
  { path: "/auth", element: authRouter },
  { path: "/<domain>", element: myRouter },   // <-- add here
];
```

---

## 11. Coding Conventions & Rules

| Convention | Rule |
|---|---|
| **Prisma access** | Always `const db = prisma as any;` in services |
| **Error throwing** | Always `throw new ApiError(httpStatus.XXX, "message")` |
| **Async controllers** | Always wrap with `catchAsync()` |
| **Responses** | Always use `sendResponse()` — never `res.json()` directly |
| **Validation** | Always validate with `validateRequest(zodSchema)` before controller |
| **Config** | Always import `config` — never use `process.env` directly |
| **Auth guard** | Use `auth()` or `auth("Admin")` on protected routes |
| **Email templates** | Create `.ejs` files in `src/app/utils/templates/` |
| **Redis keys** | Use prefix pattern: `<type>:<identifier>` e.g. `otp:user@email.com` |
| **Password hashing** | Use bcrypt with 8–10 salt rounds |
| **Module naming** | camelCase for exports, files named `<domain>.<layer>.ts` |

---

## 12. Dependencies Summary

### Production
| Package | Version | Purpose |
|---|---|---|
| `express` | ^5.2.1 | HTTP framework |
| `@prisma/client` | ^7.7.0 | Database ORM client |
| `@prisma/adapter-pg` | ^7.7.0 | PostgreSQL adapter for Prisma |
| `pg` | ^8.20.0 | PostgreSQL driver |
| `redis` | ^5.12.1 | Redis client |
| `bcrypt` | ^6.0.0 | Password hashing |
| `jsonwebtoken` | ^9.0.3 | JWT signing/verification |
| `zod` | ^4.3.6 | Schema validation |
| `nodemailer` | ^8.0.5 | Email sending |
| `ejs` | ^5.0.2 | Email HTML template engine |
| `cookie-parser` | ^1.4.7 | Cookie parsing middleware |
| `cors` | ^2.8.6 | Cross-origin middleware |
| `dotenv` | ^17.4.2 | Environment variable loading |
| `http-status` | ^2.1.0 | HTTP status code constants |

### Dev
| Package | Purpose |
|---|---|
| `typescript` | ^6.0.3 | TypeScript compiler |
| `ts-node-dev` | ^2.0.0 | Dev server with hot reload |
| `prisma` | ^7.7.0 | Prisma CLI (migrations, generate) |
| `@types/*` | Type definitions for all prod packages |

---

## 13. Scripts

```bash
npm run dev     # Start dev server (ts-node-dev --respawn --transpile-only ./src/server.ts)
```

**Prisma commands:**
```bash
npx prisma migrate dev --name <name>   # Create and apply migration
npx prisma generate                     # Regenerate Prisma Client
npx prisma studio                       # Open Prisma Studio GUI
```

---

## 14. Important Notes for AI Assistants

1. **When asked to add a new feature**, always follow the 7-step module creation pattern in Section 10.
2. **Do NOT** access `process.env` directly — always use `config` from `src/app/config/index.ts`.
3. **Do NOT** call `res.json()` directly — always use `sendResponse()`.
4. **Do NOT** write raw async try/catch in controllers — use `catchAsync()`.
5. **When adding new Prisma models**, create a separate `<domain>Schema.prisma` file and run migrate + generate.
6. **The generated Prisma client** is at `generated/prisma` (not the default `node_modules/.prisma`).
7. **Redis** is used for temporary storage (OTPs, sessions). Key format: `<type>:<identifier>`.
8. **Email templates** are EJS files at `src/app/utils/templates/<name>.ejs`. Always create `.ejs` when adding new email types.
9. **Auth guard** `auth()` attaches `req.user = { id, email, name, role }` — accessible in controllers as `req.user`.
10. **Pagination** — use `QueryBuilder` for all list endpoints. Always return `meta` in the response.
11. **APIFY_TOKEN** is available in config for future web scraping integrations.
12. **The project uses `ERole` enum** — valid roles are `"Admin"` and `"User"` only.
