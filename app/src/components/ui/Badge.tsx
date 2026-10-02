import * as React from "react";
import { cn } from "../../lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "success" | "warning" | "error" | "outline";
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2",
        {
          "border-transparent bg-neutral-100 text-neutral-900": variant === "default",
          "border-transparent bg-success-50 text-success-600": variant === "success",
          "border-transparent bg-warning-50 text-warning-600": variant === "warning",
          "border-transparent bg-error-50 text-error-600": variant === "error",
          "text-neutral-900": variant === "outline",
        },
        className
      )}
      {...props}
    />
  );
}

export { Badge };
