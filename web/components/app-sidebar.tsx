"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Map,
  Flame,
  SearchCheck,
  GitBranch,
  Share2,
  Library,
  Settings,
  FlaskConical,
  MessageCircle,
  PackageOpen,
  FolderTree,
} from "lucide-react";

import { cn } from "@/lib/utils";

const PRIMARY_NAV_ITEMS = [
  { href: "/research-map", label: "Research Map", icon: Map },
  { href: "/hotspots", label: "Hotspots", icon: Flame },
  { href: "/research-gaps", label: "Research Gaps", icon: SearchCheck },
  { href: "/topic-explorer", label: "Topic Explorer", icon: GitBranch },
  { href: "/knowledge-network", label: "Knowledge Network", icon: Share2 },
  { href: "/chat", label: "Chat", icon: MessageCircle },
] as const;

const SECONDARY_NAV_ITEMS = [
  { href: "/import", label: "Import", icon: PackageOpen },
  { href: "/assets", label: "Assets", icon: FolderTree },
  { href: "/library", label: "Library", icon: Library },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-40 flex w-56 flex-col bg-sidebar text-sidebar-foreground border-r border-sidebar-border">
      {/* Brand */}
      <div className="flex h-14 items-center gap-2.5 px-4 border-b border-sidebar-border">
        <div className="flex size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
          <FlaskConical className="size-4" strokeWidth={2} />
        </div>
        <div className="flex flex-col leading-tight">
          <span className="text-sm font-semibold tracking-tight">Scientra Copilot</span>
          <span className="text-[10px] text-sidebar-foreground/50 font-medium">
            Intelligence Platform
          </span>
        </div>
      </div>

      {/* Primary Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 scrollbar-thin">
        <p className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-sidebar-foreground/35">
          Analysis
        </p>
        <ul className="flex flex-col gap-0.5 mb-4" role="list">
          {PRIMARY_NAV_ITEMS.map((item) => {
            const isActive = pathname.startsWith(item.href);
            const Icon = item.icon;

            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "group flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-sidebar-accent text-sidebar-accent-foreground"
                      : "text-sidebar-foreground/70 hover:bg-sidebar-accent/40 hover:text-sidebar-foreground"
                  )}
                >
                  <Icon
                    className={cn(
                      "size-4 shrink-0 transition-colors",
                      isActive
                        ? "text-sidebar-accent-foreground"
                        : "text-sidebar-foreground/50 group-hover:text-sidebar-foreground/80"
                    )}
                    strokeWidth={isActive ? 2.5 : 2}
                  />
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>

        <p className="px-3 mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-sidebar-foreground/35">
          Data
        </p>
        <ul className="flex flex-col gap-0.5" role="list">
          {SECONDARY_NAV_ITEMS.map((item) => {
            const isActive = pathname.startsWith(item.href);
            const Icon = item.icon;

            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "group flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-sidebar-accent text-sidebar-accent-foreground"
                      : "text-sidebar-foreground/70 hover:bg-sidebar-accent/40 hover:text-sidebar-foreground"
                  )}
                >
                  <Icon
                    className={cn(
                      "size-4 shrink-0 transition-colors",
                      isActive
                        ? "text-sidebar-accent-foreground"
                        : "text-sidebar-foreground/50 group-hover:text-sidebar-foreground/80"
                    )}
                    strokeWidth={isActive ? 2.5 : 2}
                  />
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Footer */}
      <div className="border-t border-sidebar-border px-4 py-3">
        <p className="text-[10px] text-sidebar-foreground/40">
          Scientra Copilot v1.5
        </p>
      </div>
    </aside>
  );
}
