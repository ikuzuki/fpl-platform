import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Dashboard error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
          <div className="text-center max-w-md px-6">
            <h1 className="text-2xl font-bold mb-2">Something went wrong</h1>
            <p className="text-[var(--muted-foreground)] mb-4">
              {this.state.error?.message ?? "An unexpected error occurred"}
            </p>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
              className="rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-[var(--accent-foreground)] hover:opacity-90 transition-opacity"
            >
              Reload dashboard
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
