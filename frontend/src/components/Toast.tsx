import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react'

type ToastVariant = 'success' | 'error' | 'info' | 'warning'

interface ToastItem {
  id: number
  message: string
  variant: ToastVariant
  duration: number
}

interface ToastContextType {
  toast: (message: string, variant?: ToastVariant, duration?: number) => void
}

const ToastContext = createContext<ToastContextType>({ toast: () => {} })

export function useToast() {
  return useContext(ToastContext)
}

let nextId = 0

const VARIANT_STYLES: Record<ToastVariant, string> = {
  success: 'border-emerald-500/50 bg-emerald-950/90 text-emerald-200',
  error: 'border-red-500/50 bg-red-950/90 text-red-200',
  info: 'border-signal-teal/50 bg-base-900/95 text-ink-100',
  warning: 'border-amber-500/50 bg-amber-950/90 text-amber-200',
}

const VARIANT_ICONS: Record<ToastVariant, string> = {
  success: '✓',
  error: '✕',
  info: 'ℹ',
  warning: '⚠',
}

const VARIANT_DOT_COLORS: Record<ToastVariant, string> = {
  success: 'bg-emerald-400',
  error: 'bg-red-400',
  info: 'bg-signal-teal',
  warning: 'bg-amber-400',
}

function ToastSlot({ item, onDismiss }: { item: ToastItem; onDismiss: (id: number) => void }) {
  const [exiting, setExiting] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => {
      setExiting(true)
      setTimeout(() => onDismiss(item.id), 300)
    }, item.duration)
    return () => clearTimeout(timer)
  }, [item.id, item.duration, onDismiss])

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={`flex items-center gap-3 px-4 py-3 rounded-lg border backdrop-blur-sm shadow-xl
        ${VARIANT_STYLES[item.variant]}
        ${exiting ? 'animate-toast-exit' : 'animate-toast-enter'}
        max-w-sm w-full pointer-events-auto cursor-pointer`}
      onClick={() => {
        setExiting(true)
        setTimeout(() => onDismiss(item.id), 300)
      }}
    >
      <span className={`w-2 h-2 rounded-full shrink-0 ${VARIANT_DOT_COLORS[item.variant]}`} />
      <span className="text-xs font-medium flex-1 leading-relaxed">{item.message}</span>
      <span className="text-[10px] font-mono opacity-60 shrink-0">{VARIANT_ICONS[item.variant]}</span>
    </div>
  )
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])

  const toast = useCallback((message: string, variant: ToastVariant = 'info', duration = 4000) => {
    const id = ++nextId
    setItems((prev) => [...prev.slice(-4), { id, message, variant, duration }])
  }, [])

  const dismiss = useCallback((id: number) => {
    setItems((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      {/* Toast container — fixed bottom-right */}
      <div className="fixed bottom-4 right-4 z-[99998] flex flex-col gap-2 pointer-events-none" aria-label="Notifications">
        {items.map((item) => (
          <ToastSlot key={item.id} item={item} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}
