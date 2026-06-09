import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "D.R.O.N.A. — Bias-Aware Academic Advising",
  description:
    "Dynamic Robotic Operations for Navigational Assistance — a locally-grounded, bias-aware academic and career advising dashboard.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-gradient-to-b from-muted/40 to-background antialiased">
        {children}
      </body>
    </html>
  );
}
