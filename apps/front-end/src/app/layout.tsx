import type { Metadata } from 'next';
import { IBM_Plex_Mono, Manrope } from 'next/font/google';

import { AppProviders } from '@/components/providers';

import './globals.css';

const manrope = Manrope({
  subsets: ['latin'],
  variable: '--font-manrope',
});

const mono = IBM_Plex_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  weight: ['400', '500'],
});

export const metadata: Metadata = {
  title: 'AI Stack Admin Portal',
  description: 'Premium dark admin portal for AI Stack operations.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${manrope.variable} ${mono.variable} font-[family-name:var(--font-manrope)] antialiased`}>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
