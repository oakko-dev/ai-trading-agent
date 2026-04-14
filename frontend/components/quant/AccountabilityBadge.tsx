"use client";

import { cn } from "@/lib/utils";

const CLASSIFICATIONS = {
  skilled_win: { label: "Skilled Win", color: "text-green-500", bg: "bg-green-500/10" },
  correct_process: { label: "Correct Process", color: "text-blue-500", bg: "bg-blue-500/10" },
  lucky_win: { label: "Lucky", color: "text-yellow-500", bg: "bg-yellow-500/10" },
  real_mistake: { label: "Mistake", color: "text-red-500", bg: "bg-red-500/10" },
} as const;

interface AccountabilityBadgeProps {
  classification: string;
  className?: string;
}

export function AccountabilityBadge({ classification, className }: AccountabilityBadgeProps) {
  const config = CLASSIFICATIONS[classification as keyof typeof CLASSIFICATIONS] || CLASSIFICATIONS.correct_process;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold",
        config.bg,
        config.color,
        className,
      )}
    >
      {config.label}
    </span>
  );
}
