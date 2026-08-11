"use client";
import { CheckCircle2, X, XCircle } from "lucide-react";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
type Toast = { id: number; message: string; tone: "success" | "error" };
const ToastContext = createContext<(message: string, tone?: Toast["tone"]) => void>(() => undefined);
export const useToast = () => useContext(ToastContext);
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const notify = useCallback((message: string, tone: Toast["tone"] = "success") => { const id = Date.now(); setToasts(current => [...current, { id, message, tone }]); setTimeout(() => setToasts(current => current.filter(item => item.id !== id)), 4500); }, []);
  return <ToastContext.Provider value={notify}>{children}<div className="toast-stack">{toasts.map(toast => <div key={toast.id} className={`toast ${toast.tone}`}>{toast.tone === "success" ? <CheckCircle2 size={18}/> : <XCircle size={18}/>}<span>{toast.message}</span><button onClick={() => setToasts(current => current.filter(item => item.id !== toast.id))} aria-label="Dismiss"><X size={14}/></button></div>)}</div></ToastContext.Provider>;
}

