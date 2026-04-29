"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/conservative", label: "Conservador" },
  { href: "/aggressive", label: "Agresivo" },
  { href: "/ranking", label: "Ranking" },
  { href: "/macro", label: "Macro" },
  { href: "/settings", label: "Ajustes" },
];

export function Header() {
  const pathname = usePathname();
  return (
    <header className="border-b border-ink/15 bg-paper/80 backdrop-blur-sm sticky top-0 z-20">
      <div className="max-w-[1400px] mx-auto px-6 py-4 flex items-baseline gap-8">
        <Link href="/" className="display-heading text-2xl tracking-tightest leading-none">
          Long<span className="text-bull">·</span>Radar
        </Link>
        <nav className="flex gap-6 text-sm">
          {NAV.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`hover:text-bull transition-colors ${
                  active
                    ? "text-bull border-b border-bull pb-1 font-medium"
                    : "text-ink/70"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto text-xs uppercase tracking-widest text-ink-muted font-mono">
          v0.3 · NOT FINANCIAL ADVICE
        </div>
      </div>
    </header>
  );
}