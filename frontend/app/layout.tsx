import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";
import { ToastProvider } from "@/components/Toast";

export const metadata: Metadata = { title: { default: "AFTER OURS", template: "%s · AFTER OURS" }, description: "Self-hosted content discovery, clipping, review, scheduling and publishing control room.", robots: { index: false, follow: false } };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><ToastProvider><Sidebar/><main className="main"><div className="top-strip"><span>AFTER OURS / CONTROL ROOM</span><div><i/> System-connected workspace</div></div><div className="page">{children}</div></main></ToastProvider></body></html>;
}

