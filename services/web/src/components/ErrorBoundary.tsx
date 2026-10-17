import { Component, ErrorInfo, ReactNode } from "react";
import { AlertOctagon, RotateCcw } from "lucide-react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  traceId: string | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    traceId: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    const traceId = (error as any).traceId || "selene-trace-" + Math.random().toString(36).substring(2, 9);
    return { hasError: true, error, traceId };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught frontend error:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-space-dark flex items-center justify-center p-6 text-gray-100">
          <div className="glass-panel p-8 max-w-lg w-full flex flex-col gap-5 border-rose-500/30 text-center items-center">
            <div className="w-12 h-12 rounded-full bg-rose-500/20 border border-rose-500/40 flex items-center justify-center">
              <AlertOctagon className="w-6 h-6 text-rose-400" />
            </div>

            <div>
              <h2 className="text-xl font-bold text-white">Application Exception Encountered</h2>
              <p className="text-xs text-gray-400 mt-1">
                {this.state.error?.message || "An unexpected error interrupted this session."}
              </p>
            </div>

            <div className="bg-black/60 border border-white/10 rounded-lg p-3 w-full text-xs font-mono text-gray-300">
              <span className="text-gray-500 block text-[10px]">TRACE ID FOR SUPPORT:</span>
              <span className="text-cyan-400 font-bold select-all">{this.state.traceId}</span>
            </div>

            <button
              onClick={() => window.location.reload()}
              className="btn-primary"
            >
              <RotateCcw className="w-4 h-4" />
              <span>Reload Application</span>
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
