"use client";

import { useState } from "react";
import { Check, ChevronsUpDown, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList, CommandSeparator } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { Brand } from "@/lib/types";
import { cn } from "@/lib/utils";

export function BrandSwitcher({
  brands,
  activeId,
  isNew,
  onSelect,
  onNew,
  disabled,
}: {
  brands: Brand[];
  activeId: string | null;
  isNew: boolean;
  onSelect: (id: string) => void;
  onNew: () => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const active = brands.find((b) => b.id === activeId);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" role="combobox" aria-expanded={open} aria-label="Switch brand" disabled={disabled} className="max-w-[46vw] justify-between gap-2 rounded-full sm:w-56">
          <span className="truncate">{isNew ? "New brand" : (active?.name ?? "Choose a brand")}</span>
          <ChevronsUpDown className="size-3.5 shrink-0 opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-0" align="end">
        <Command>
          {brands.length > 5 && <CommandInput placeholder="Find a brand" />}
          <CommandList>
            <CommandEmpty>No brand with that name.</CommandEmpty>
            {brands.length > 0 && (
              <CommandGroup heading="Your brands">
                {brands.map((b) => (
                  <CommandItem
                    key={b.id}
                    value={`${b.name} ${b.id}`}
                    onSelect={() => {
                      onSelect(b.id);
                      setOpen(false);
                    }}
                  >
                    <span className="truncate">{b.name}</span>
                    <Check className={cn("ml-auto size-4", b.id === activeId && !isNew ? "opacity-100" : "opacity-0")} />
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
            <CommandSeparator />
            <CommandGroup>
              <CommandItem
                value="new-brand"
                onSelect={() => {
                  onNew();
                  setOpen(false);
                }}
              >
                <Plus className="size-4" /> New brand
              </CommandItem>
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
