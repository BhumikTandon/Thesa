import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";

const clerkAppearance = {
  variables: {
    colorBackground: "#101018",
    colorInputBackground: "#16161f",
    colorText: "#ededf2",
    colorInputText: "#ededf2",
    colorTextSecondary: "#8b8b9a",
    // Neutral drives borders, dividers, and social (Google/etc.) button
    // text — must be light or those buttons vanish on the dark background.
    colorNeutral: "#ededf2",
    colorPrimary: "#34d399",
    colorDanger: "#f87171",
    borderRadius: "0.75rem",
  },
  elements: {
    socialButtonsBlockButton: {
      backgroundColor: "#1c1c26",
      border: "1px solid #2e2e3a",
      color: "#ededf2",
    },
  },
};

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Thesa",
  description:
    "Rewards-neutral spend management for field workforces. Route every dollar to the highest-earning card.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider appearance={clerkAppearance}>
      <html
        lang="en"
        className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      >
        <body className="min-h-full flex flex-col">{children}</body>
      </html>
    </ClerkProvider>
  );
}
