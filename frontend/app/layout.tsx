import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Talent Intelligence AI",
  description: "AI-powered recruitment intelligence platform for resume ranking and hidden-fit discovery.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
