import * as React from "react";
import { cn } from "../../lib/utils";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "ghost" | "danger";
  size?: "sm" | "md" | "lg" | "icon";
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 disabled:pointer-events-none disabled:opacity-50",
          {
            "bg-primary-600 text-white hover:bg-primary-700 shadow-sm": variant === "primary",
            "bg-primary-50 text-primary-700 hover:bg-primary-100": variant === "secondary",
            "border border-neutral-200 bg-white hover:bg-neutral-100 text-neutral-900": variant === "outline",
            "hover:bg-neutral-100 text-neutral-700": variant === "ghost",
            "bg-error-50 text-error-600 hover:bg-error-100": variant === "danger",
            
            "h-9 px-4 py-2": size === "md",
            "h-8 rounded-md px-3 text-xs": size === "sm",
            "h-11 rounded-md px-8 text-base": size === "lg",
            "h-10 w-10": size === "icon",
          },
          className
        )}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button };
