import * as React from "react"
import { cn } from "@/lib/utils"

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost'
  size?: 'sm' | 'md' | 'lg' | 'icon'
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center rounded-full font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--orange)] disabled:opacity-50 disabled:pointer-events-none active:scale-95",
          {
            "bg-[var(--green)] text-white hover:bg-[var(--green)]/90": variant === 'primary',
            "bg-[var(--surface-2)] text-[var(--ink)] hover:bg-[var(--line)]": variant === 'secondary',
            "border border-[var(--line)] bg-transparent hover:bg-[var(--surface-2)]": variant === 'outline',
            "hover:bg-[var(--surface-2)] hover:text-[var(--ink)]": variant === 'ghost',
            "h-9 px-4 text-sm": size === 'sm',
            "h-11 px-6 text-base": size === 'md',
            "h-[52px] px-8 text-lg": size === 'lg',
            "h-11 w-11": size === 'icon',
          },
          className
        )}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button }
