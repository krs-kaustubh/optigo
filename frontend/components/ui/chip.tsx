import * as React from "react"
import { cn } from "@/lib/utils"

export interface ChipProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'train' | 'metro' | 'walk' | 'outline';
}

export function Chip({ className, variant = 'default', ...props }: ChipProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full px-3 py-1 text-xs font-medium uppercase tracking-wider",
        {
          "bg-[var(--surface-2)] text-[var(--ink-muted)]": variant === 'default',
          "bg-[var(--green-soft)] text-[var(--green)]": variant === 'train',
          "bg-[var(--orange-soft)] text-[var(--orange)]": variant === 'metro',
          "bg-[var(--line)] text-[var(--ink-muted)]": variant === 'walk',
          "border border-[var(--line)] text-[var(--ink-muted)]": variant === 'outline',
        },
        className
      )}
      {...props}
    />
  )
}
