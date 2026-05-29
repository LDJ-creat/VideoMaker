"use client";

import type { VariantDefinition } from "@videomaker/contracts";

import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { getEnabledVariants } from "@/lib/variantRegistry";
import { cn } from "@/lib/utils";

type VariantPickerProps = {
  selectedVariantIds: string[];
  onChange: (variantIds: string[]) => void;
  variants?: VariantDefinition[];
  disabled?: boolean;
  className?: string;
};

export function VariantPicker({
  selectedVariantIds,
  onChange,
  variants = getEnabledVariants(),
  disabled,
  className,
}: VariantPickerProps) {
  const toggleVariant = (variantId: string) => {
    if (disabled) return;
    if (selectedVariantIds.includes(variantId)) {
      if (selectedVariantIds.length <= 1) return;
      onChange(selectedVariantIds.filter((id) => id !== variantId));
      return;
    }
    onChange([...selectedVariantIds, variantId]);
  };

  return (
    <fieldset
      className={cn("space-y-2", className)}
      data-testid="variant-picker"
      disabled={disabled}
    >
      <legend className="text-sm font-medium">生成变体</legend>
      <p className="text-xs text-muted-foreground">
        默认选中全部已启用变体（高点击 + 高转化）
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        {variants.map((variant) => {
          const checked = selectedVariantIds.includes(variant.id);
          return (
            <label
              key={variant.id}
              className={cn(
                "flex cursor-pointer gap-3 rounded-lg border p-3 transition-colors",
                checked ? "border-ai/50 bg-ai/5" : "border-border",
                disabled && "cursor-not-allowed opacity-60",
              )}
            >
              <input
                type="checkbox"
                className="mt-1"
                checked={checked}
                disabled={disabled}
                onChange={() => toggleVariant(variant.id)}
                aria-label={variant.label}
              />
              <span className="space-y-1">
                <span className="flex items-center gap-2">
                  <Label className="cursor-pointer font-medium">
                    {variant.label}
                  </Label>
                  <Badge variant="outline" className="font-mono text-[10px]">
                    {variant.id}
                  </Badge>
                </span>
                {variant.description && (
                  <span className="block text-xs text-muted-foreground">
                    {variant.description}
                  </span>
                )}
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

export function getDefaultSelectedVariantIds(): string[] {
  return getEnabledVariants().map((variant) => variant.id);
}
