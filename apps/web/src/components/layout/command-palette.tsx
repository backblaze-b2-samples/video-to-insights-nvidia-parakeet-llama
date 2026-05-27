"use client";

import { useRouter } from "next/navigation";
import { LayoutDashboard, Plus, FolderOpen, Moon, Sun, Sparkles } from "lucide-react";
import { useTheme } from "next-themes";

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// Three routes — keep this synced with app-sidebar.tsx.
const routes = [
  { label: "Go to Dashboard", href: "/", icon: LayoutDashboard },
  { label: "New job", href: "/new", icon: Plus },
  { label: "Browse files", href: "/files", icon: FolderOpen },
];

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const router = useRouter();
  const { setTheme } = useTheme();

  const runThen = (fn: () => void) => () => {
    onOpenChange(false);
    fn();
  };

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder="Search or jump to a page..." />
      <CommandList>
        <CommandEmpty>No matches found.</CommandEmpty>
        <CommandGroup heading="Navigate">
          {routes.map((r) => (
            <CommandItem
              key={r.href}
              onSelect={runThen(() => router.push(r.href))}
              value={`nav ${r.label}`}
            >
              <r.icon />
              {r.label}
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="Theme">
          <CommandItem onSelect={runThen(() => setTheme("light"))} value="theme light">
            <Sun />
            Light mode
          </CommandItem>
          <CommandItem onSelect={runThen(() => setTheme("dark"))} value="theme dark">
            <Moon />
            Dark mode
          </CommandItem>
          <CommandItem onSelect={runThen(() => setTheme("system"))} value="theme system">
            <Sparkles />
            System theme
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
