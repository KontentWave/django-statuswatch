import {
  calculatePasswordStrength,
  checkPasswordRequirements,
  getStrengthColor,
  getStrengthLabel,
  type PasswordStrength,
} from "@/lib/password-strength";

interface PasswordStrengthIndicatorProps {
  password: string;
  showRequirements?: boolean;
}

export function PasswordStrengthIndicator({
  password,
  showRequirements = true,
}: PasswordStrengthIndicatorProps) {
  const strength = calculatePasswordStrength(password);
  const requirements = checkPasswordRequirements(password);

  if (!password) return null;

  return (
    <div className="space-y-2 text-sm">
      {/* Strength bar */}
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            Password strength
          </span>
          {strength !== "empty" && (
            <span
              className={`text-xs font-medium ${
                strength === "strong"
                  ? "text-green-600"
                  : strength === "good"
                  ? "text-yellow-600"
                  : strength === "fair"
                  ? "text-orange-600"
                  : "text-red-600"
              }`}
            >
              {getStrengthLabel(strength)}
            </span>
          )}
        </div>
        <div className="flex gap-1">
          {[1, 2, 3, 4].map((bar) => (
            <div
              key={bar}
              className={`h-1 flex-1 rounded-full transition-colors ${getStrengthBarColor(
                strength,
                bar
              )}`}
            />
          ))}
        </div>
      </div>

      {/* Requirements checklist */}
      {showRequirements && (
        <ul className="space-y-1 text-xs">
          <RequirementItem
            met={requirements.minLength}
            label="At least 12 characters"
          />
          <RequirementItem
            met={requirements.hasUppercase}
            label="One uppercase letter"
          />
          <RequirementItem
            met={requirements.hasLowercase}
            label="One lowercase letter"
          />
          <RequirementItem met={requirements.hasNumber} label="One number" />
          <RequirementItem
            met={requirements.hasSpecialChar}
            label="One special character (!@#$%^&*...)"
          />
        </ul>
      )}
    </div>
  );
}

interface RequirementItemProps {
  met: boolean;
  label: string;
}

function RequirementItem({ met, label }: RequirementItemProps) {
  return (
    <li
      className={`flex items-center gap-2 ${
        met ? "text-green-600" : "text-muted-foreground"
      }`}
    >
      <span className="text-base">{met ? "✓" : "○"}</span>
      <span>{label}</span>
    </li>
  );
}

/**
 * Get color for individual strength bar segments
 */
function getStrengthBarColor(
  strength: PasswordStrength,
  barIndex: number
): string {
  const strengthLevels = {
    empty: 0,
    weak: 1,
    fair: 2,
    good: 3,
    strong: 4,
  };

  const level = strengthLevels[strength];

  if (barIndex > level) {
    return "bg-gray-200";
  }

  return getStrengthColor(strength);
}
