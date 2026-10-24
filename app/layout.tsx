import "./globals.css";
import Link from "next/link";
import type { ReactNode } from "react";

export const metadata = { title: "Code Apex - QA dashboard", description: "Autonomous AI QA engineer" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="topbar"><Link href="/">Code Apex</Link><span className="muted">Autonomous QA runs</span></header>
        <main>{children}</main>
      </body>
    </html>
  );
}
