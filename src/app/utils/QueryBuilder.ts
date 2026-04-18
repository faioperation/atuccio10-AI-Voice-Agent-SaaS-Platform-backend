// ─── Types ───────────────────────────────────────────────────────────────────

/** Raw query params from req.query */
export type TQueryInput = Record<string, string | string[] | undefined>;

/** Maps relation name to its filterable/searchable fields */
export type TRelationConfig = Record<string, string[]>;

/** Search config: either a plain field name or { relation: [fields] } */
export type TSearchConfigItem = string | Record<string, string[]>;
export type TSearchConfig = TSearchConfigItem[];

/** The built Prisma query args */
export type TQueryBuilderResult = {
  where: Record<string, any>;
  orderBy?: Record<string, any> | Record<string, any>[];
  select?: Record<string, boolean>;
  skip?: number;
  take?: number;
};

/** Pagination meta returned alongside data */
export type TPaginationMeta = {
  page: number;
  limit: number;
  total: number;
  totalPage: number;
};

// ─── Fields excluded from filters ─────────────────────────────────────────────
const excludeFields: string[] = [
  "searchTerm",
  "searchParam",
  "sort",
  "orderBy",
  "page",
  "limit",
  "fields",
  "skip",
  "take",
];

// ─── QueryBuilder ─────────────────────────────────────────────────────────────

export class QueryBuilder {
  private query: TQueryInput;
  public where: Record<string, any>;
  public orderBy: Record<string, any> | Record<string, any>[] | undefined;
  public select: Record<string, boolean> | undefined;
  public skip: number | undefined;
  public take: number | undefined;

  constructor(query: TQueryInput) {
    this.query = query;
    this.where = {};
    this.orderBy = undefined;
    this.select = undefined;
    this.skip = undefined;
    this.take = undefined;
  }

  /** Apply exact-match filters from query params (case-insensitive for strings) */
  filter(relationConfig: TRelationConfig = {}): this {
    const filters = { ...this.query };

    [...excludeFields].forEach((field) => delete filters[field]);

    Object.entries(filters).forEach(([key, value]) => {
      if (value === undefined || value === "") return;

      let finalValue: any = value;

      // Case-insensitive mode for plain strings that are not numbers/booleans
      if (
        typeof value === "string" &&
        isNaN(Number(value)) &&
        value.toLowerCase() !== "true" &&
        value.toLowerCase() !== "false"
      ) {
        finalValue = { equals: value, mode: "insensitive" };
      }

      let isRelational = false;

      for (const [relation, fields] of Object.entries(relationConfig)) {
        if (fields.includes(key)) {
          this.where[relation] = {
            ...(this.where[relation] ?? {}),
            [key]: finalValue,
          };
          isRelational = true;
          break;
        }
      }

      if (!isRelational) {
        this.where[key] = finalValue;
      }
    });

    return this;
  }

  /** Select only specified fields (comma-separated in query: ?fields=name,email) */
  fields(): this {
    const fieldsParam = this.query.fields;
    if (fieldsParam && typeof fieldsParam === "string") {
      const selectObj: Record<string, boolean> = {};
      fieldsParam.split(",").forEach((f) => {
        selectObj[f.trim()] = true;
      });
      this.select = selectObj;
    }
    return this;
  }

  /** Full-text search across plain fields and relation fields */
  search(searchConfig: TSearchConfig = []): this {
    const searchTerm =
      (this.query.searchTerm as string) ?? (this.query.searchParam as string);

    if (!searchTerm || !searchConfig.length) return this;

    this.where.OR = searchConfig.map((field) => {
      // Plain field
      if (typeof field === "string") {
        return {
          [field]: { contains: searchTerm, mode: "insensitive" },
        };
      }

      // Relation field: { relation: [field1, field2] }
      const [relation, relationFields] = Object.entries(field)[0] as [
        string,
        string[],
      ];
      return {
        [relation]: {
          OR: relationFields.map((rf) => ({
            [rf]: { contains: searchTerm, mode: "insensitive" },
          })),
        },
      };
    });

    return this;
  }

  /**
   * Sort: ?sort=-followerCount (desc), ?sort=name (asc), ?sort=name desc
   * Supports comma-separated multi-sort
   */
  sort(
    defaultSort: string = "createdAt",
    relationConfig: TRelationConfig = {},
  ): this {
    const rawSort = (this.query.sort as string) ?? defaultSort;

    const sortFields: Record<string, any>[] = rawSort
      .split(",")
      .map((field) => {
        field = field.trim();
        let order: "asc" | "desc" = "asc";
        let column = field;

        if (field.startsWith("-")) {
          column = field.slice(1);
          order = "desc";
        } else {
          const parts = field.split(/\s+/);
          if (parts.length > 1) {
            column = parts[0];
            order = parts[1].toLowerCase() === "desc" ? "desc" : "asc";
          } else if (
            field.toLowerCase() === "desc" ||
            field.toLowerCase() === "asc"
          ) {
            return { [defaultSort]: field.toLowerCase() as "asc" | "desc" };
          }
        }

        // Check if belongs to a relation
        for (const [relation, fields] of Object.entries(relationConfig)) {
          if (fields.includes(column)) {
            return { [relation]: { [column]: order } };
          }
        }

        return { [column]: order };
      });

    this.orderBy = sortFields.length > 1 ? sortFields : sortFields[0];
    return this;
  }

  /** Apply page/limit pagination */
  paginate(): this {
    const page = Number(this.query.page) || 1;
    const limit = Number(this.query.limit) || 15;
    this.skip = (page - 1) * limit;
    this.take = limit;
    return this;
  }

  /** Build and return the full Prisma query args object */
  build(): TQueryBuilderResult {
    return {
      where: this.where,
      orderBy: this.orderBy,
      select: this.select,
      skip: this.skip,
      take: this.take,
    };
  }

  /** Return pagination meta — call after getting total count from DB */
  getMeta(total: number): TPaginationMeta {
    const page = Number(this.query.page) || 1;
    const limit = Number(this.query.limit) || 15;
    return {
      page,
      limit,
      total,
      totalPage: Math.ceil(total / limit),
    };
  }
}