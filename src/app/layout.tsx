import type { Metadata, Viewport } from "next";
import "@fontsource-variable/inter/wght.css"; // self-hosted, so no request to Google and no layout shift
import { Toaster } from "@/components/Toaster";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Meeting Scheduler", template: "%s · Meeting Scheduler" },
  description: "Midweek and weekend assignments, S-89 slips and the S-140",
};

export const viewport: Viewport = {
  width: "device-width", initialScale: 1, viewportFit: "cover",
  themeColor: [{ media: "(prefers-color-scheme: light)", color: "#F6F7F9" },
    { media: "(prefers-color-scheme: dark)", color: "#0F1620" }],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-GB">
      <body><Toaster>{children}</Toaster></body>
    </html>
  );
}
