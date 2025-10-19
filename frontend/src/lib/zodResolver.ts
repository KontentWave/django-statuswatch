import type {
  FieldErrors,
  FieldValues,
  ResolverOptions,
  ResolverResult,
} from "react-hook-form";
import { type ZodSchema, type ZodError } from "zod";

/**
 * Custom zodResolver that works reliably in test environments
 * Based on @hookform/resolvers/zod but with explicit error handling
 */
export function customZodResolver<T extends ZodSchema>(schema: T) {
  return async <TFieldValues extends FieldValues, TContext>(
    values: TFieldValues,
    _context: TContext | undefined,
    _options: ResolverOptions<TFieldValues>
  ): Promise<ResolverResult<TFieldValues>> => {
    try {
      const data = await schema.parseAsync(values);
      return {
        values: data as TFieldValues,
        errors: {},
      };
    } catch (error) {
      // Explicitly handle ZodError
      if (error && typeof error === "object" && "issues" in error) {
        const zodError = error as ZodError;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const fieldErrors: Record<string, any> = {};

        for (const issue of zodError.issues) {
          const path = issue.path.join(".");
          if (!fieldErrors[path]) {
            fieldErrors[path] = {
              type: issue.code,
              message: issue.message,
            };
          }
        }

        return {
          values: {} as Record<string, never>,
          errors: fieldErrors as FieldErrors<TFieldValues>,
        };
      }

      // Re-throw non-Zod errors
      throw error;
    }
  };
}
