import { Logo } from "@/components/shell/logo";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden flex-col justify-between overflow-hidden bg-side p-12 text-white lg:flex">
        <div className="absolute -right-24 -top-24 size-96 rounded-full bg-brand/30 blur-3xl" aria-hidden />
        <div className="relative flex items-center gap-3">
          <Logo size={44} />
          <div>
            <p className="text-lg font-bold tracking-wide">ALUMNI CHALLENGE</p>
            <p className="text-xs text-white/60">Connect • Support • Create Impact</p>
          </div>
        </div>
        <div className="relative max-w-md">
          <h2 className="text-4xl font-bold leading-tight">Together we build stronger communities.</h2>
          <p className="mt-4 text-white/70">
            Find fellow alumni, reconnect with your school and partners, and put your network to work.
          </p>
        </div>
        <p className="relative text-xs text-white/40">© Alumni Challenge</p>
      </div>
      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">{children}</div>
      </div>
    </div>
  );
}
