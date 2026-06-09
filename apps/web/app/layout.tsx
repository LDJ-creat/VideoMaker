import type { Metadata } from "next";
import { Geist_Mono, Noto_Sans_SC, Noto_Serif_SC } from "next/font/google";

import { AppHeader } from "@/components/app-header";
import { ThemeProvider } from "@/components/theme-provider";

import "./globals.css";

const notoSans = Noto_Sans_SC({
  variable: "--font-noto-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const notoSerif = Noto_Serif_SC({
  variable: "--font-noto-serif",
  subsets: ["latin"],
  weight: ["400", "600", "700"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "VideoMaker Workbench",
  description: "可解释的爆款视频结构迁移工作台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body
        className={`${notoSans.variable} ${notoSerif.variable} ${geistMono.variable} min-h-screen font-sans`}
      >
        <ThemeProvider attribute="class" defaultTheme="light" enableSystem>
          <AppHeader />
          <main className="mx-auto max-w-7xl px-4 pb-6 pt-14 md:px-6">
            {children}
          </main>
        </ThemeProvider>
      </body>
    </html>
  );
}
