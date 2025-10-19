import { describe, expect, it } from "vitest";
import {
  calculatePasswordStrength,
  checkPasswordRequirements,
  getStrengthColor,
  getStrengthLabel,
} from "../password-strength";

describe("Password Strength Utilities", () => {
  describe("checkPasswordRequirements", () => {
    it("identifies all requirements met for strong password", () => {
      const result = checkPasswordRequirements("MyStr0ng!P@ssword");
      expect(result.minLength).toBe(true);
      expect(result.hasUppercase).toBe(true);
      expect(result.hasLowercase).toBe(true);
      expect(result.hasNumber).toBe(true);
      expect(result.hasSpecialChar).toBe(true);
      expect(result.maxLength).toBe(true);
    });

    it("identifies missing minimum length", () => {
      const result = checkPasswordRequirements("Short1!");
      expect(result.minLength).toBe(false);
    });

    it("identifies missing uppercase", () => {
      const result = checkPasswordRequirements("lowercase123!");
      expect(result.hasUppercase).toBe(false);
    });

    it("identifies missing lowercase", () => {
      const result = checkPasswordRequirements("UPPERCASE123!");
      expect(result.hasLowercase).toBe(false);
    });

    it("identifies missing number", () => {
      const result = checkPasswordRequirements("NoNumbersHere!");
      expect(result.hasNumber).toBe(false);
    });

    it("identifies missing special character", () => {
      const result = checkPasswordRequirements("NoSpecialChar123");
      expect(result.hasSpecialChar).toBe(false);
    });

    it("identifies password exceeding max length", () => {
      const tooLong = "A".repeat(129) + "1!";
      const result = checkPasswordRequirements(tooLong);
      expect(result.maxLength).toBe(false);
    });

    it("accepts various special characters", () => {
      const specialChars = "!@#$%^&*()_+-=[]{}|;:,.<>?";
      for (const char of specialChars) {
        const password = `TestPass123${char}`;
        const result = checkPasswordRequirements(password);
        expect(result.hasSpecialChar).toBe(true);
      }
    });
  });

  describe("calculatePasswordStrength", () => {
    it('returns "empty" for empty string', () => {
      expect(calculatePasswordStrength("")).toBe("empty");
    });

    it('returns "weak" for password meeting 0-1 requirements', () => {
      expect(calculatePasswordStrength("a")).toBe("weak");
      expect(calculatePasswordStrength("123456")).toBe("weak");
    });

    it('returns "fair" for password meeting 2-3 requirements', () => {
      expect(calculatePasswordStrength("Abc123")).toBe("fair"); // 3 requirements
      expect(calculatePasswordStrength("ABC123")).toBe("fair"); // 2 requirements
    });

    it('returns "good" for password meeting 4 requirements', () => {
      expect(calculatePasswordStrength("Abc123!")).toBe("good"); // 4 requirements (missing min length)
      expect(calculatePasswordStrength("ABCDEFGHIJ12!")).toBe("good"); // 4 requirements (missing lowercase)
    });

    it('returns "strong" for password meeting all 6 requirements', () => {
      expect(calculatePasswordStrength("MyStr0ng!P@ssword")).toBe("strong");
      expect(calculatePasswordStrength("TestP@ss123456")).toBe("strong");
      expect(calculatePasswordStrength("C0mpl3x&Secure#Pass")).toBe("strong");
    });
  });

  describe("getStrengthColor", () => {
    it("returns correct color for each strength level", () => {
      expect(getStrengthColor("empty")).toBe("bg-gray-200");
      expect(getStrengthColor("weak")).toBe("bg-red-500");
      expect(getStrengthColor("fair")).toBe("bg-orange-500");
      expect(getStrengthColor("good")).toBe("bg-yellow-500");
      expect(getStrengthColor("strong")).toBe("bg-green-500");
    });
  });

  describe("getStrengthLabel", () => {
    it("returns correct label for each strength level", () => {
      expect(getStrengthLabel("empty")).toBe("");
      expect(getStrengthLabel("weak")).toBe("Weak");
      expect(getStrengthLabel("fair")).toBe("Fair");
      expect(getStrengthLabel("good")).toBe("Good");
      expect(getStrengthLabel("strong")).toBe("Strong");
    });
  });

  describe("Edge Cases", () => {
    it("handles password exactly at minimum length", () => {
      const result = checkPasswordRequirements("TestPass1!23"); // exactly 12 chars
      expect(result.minLength).toBe(true);
    });

    it("handles password exactly at maximum length", () => {
      const maxLength = "A".repeat(126) + "1!"; // exactly 128 chars
      const result = checkPasswordRequirements(maxLength);
      expect(result.maxLength).toBe(true);
      expect(result.minLength).toBe(true);
    });

    it("handles unicode characters", () => {
      const password = "TestP@ss123🔥"; // 14 chars including emoji
      const result = checkPasswordRequirements(password);
      expect(result.minLength).toBe(true);
    });

    it("handles passwords with only spaces and special chars", () => {
      const password = "!!! @@@  ###";
      const result = checkPasswordRequirements(password);
      expect(result.hasSpecialChar).toBe(true);
      expect(result.hasUppercase).toBe(false);
      expect(result.hasLowercase).toBe(false);
      expect(result.hasNumber).toBe(false);
    });
  });
});
