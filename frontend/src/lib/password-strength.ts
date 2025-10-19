/**
 * Password strength calculator for P1-01 complexity requirements
 */

export type PasswordStrength = "empty" | "weak" | "fair" | "good" | "strong";

export interface PasswordRequirements {
  minLength: boolean;
  hasUppercase: boolean;
  hasLowercase: boolean;
  hasNumber: boolean;
  hasSpecialChar: boolean;
  maxLength: boolean;
}

/**
 * Check which password requirements are met
 */
export function checkPasswordRequirements(
  password: string
): PasswordRequirements {
  return {
    minLength: password.length >= 12,
    hasUppercase: /[A-Z]/.test(password),
    hasLowercase: /[a-z]/.test(password),
    hasNumber: /\d/.test(password),
    hasSpecialChar: /[!@#$%^&*()_+\-=[\]{}|;:,.<>?]/.test(password),
    maxLength: password.length > 0 && password.length <= 128,
  };
}

/**
 * Calculate password strength based on requirements
 * Counts only the 5 core requirements (minLength, uppercase, lowercase, number, special)
 * maxLength is enforced but not counted toward strength
 */
export function calculatePasswordStrength(password: string): PasswordStrength {
  if (!password) return "empty";

  const reqs = checkPasswordRequirements(password);

  // Count only the 5 core requirements (exclude maxLength)
  const metCount = [
    reqs.minLength,
    reqs.hasUppercase,
    reqs.hasLowercase,
    reqs.hasNumber,
    reqs.hasSpecialChar,
  ].filter(Boolean).length;

  // All 5 core requirements met
  if (metCount === 5) return "strong";
  // 4 requirements met
  if (metCount === 4) return "good";
  // 2-3 requirements met
  if (metCount >= 2) return "fair";
  // 0-1 requirements met
  return "weak";
}

/**
 * Get color class for strength level
 */
export function getStrengthColor(strength: PasswordStrength): string {
  switch (strength) {
    case "empty":
      return "bg-gray-200";
    case "weak":
      return "bg-red-500";
    case "fair":
      return "bg-orange-500";
    case "good":
      return "bg-yellow-500";
    case "strong":
      return "bg-green-500";
  }
}

/**
 * Get text label for strength level
 */
export function getStrengthLabel(strength: PasswordStrength): string {
  switch (strength) {
    case "empty":
      return "";
    case "weak":
      return "Weak";
    case "fair":
      return "Fair";
    case "good":
      return "Good";
    case "strong":
      return "Strong";
  }
}
