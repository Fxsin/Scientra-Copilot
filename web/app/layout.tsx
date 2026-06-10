import type { Metadata } from "next";
import { LayoutShell } from "@/components/layout-shell";
import { QueryProvider } from "@/components/query-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Scientra Copilot — Research OS",
  description:
    "AI-Powered Research Discovery Platform — From Literature to Discovery.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="scrollbar-thin">
      <body>
        <QueryProvider>
          <LayoutShell>{children}</LayoutShell>
        </QueryProvider>
      </body>
    </html>
  );
}
