import React from "react";

interface Props {
    children: React.ReactNode;
    fallback: React.ReactNode;
}

interface State {
    hasError: boolean;
}

class ErrorBoundary extends React.Component<Props, State> {
    state = { hasError: false }

    static getDerivedStateError() {
        //Update state so the next render will show the fallback UI
        return { hasError: true }
    }

    render () {
        //if 'hasError' is true, a fallback is rendered
        if (this.state.hasError){
            return this.props.fallback;
        }

        //Otherwise, render children as normal
        return this.props.children;
    }
}

export default ErrorBoundary;