import type { Metadata } from "next";
import { SpeedInsights } from "@vercel/speed-insights/next";

export const metadata: Metadata = {
  title: "Mulberry",
  description: "Mulberry app shell (Next.js)",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ro">
      <body style={{ margin: 0, fontFamily: "system-ui, sans-serif" }}>
        {children}
        <SpeedInsights />
      </body>
    </html>
  );
}
