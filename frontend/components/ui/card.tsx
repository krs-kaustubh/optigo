import * as React from "react"
import { cn } from "@/lib/utils"

const Card = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "rounded-[20px] border border-[var(--line)] bg-[var(--surface)] shadow-sm transition-all",
      className
    )}
    {...props}
  />
))
Card.displayName = "Card"

export { Card }
