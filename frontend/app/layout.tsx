import type { Metadata } from "next";
import "@fontsource-variable/dm-sans";
import "./globals.css";

export const metadata: Metadata = {
  title: "VidyaPath | Learning Studio",
  description: "A trusted, adaptive learning workspace for faculty and students.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}