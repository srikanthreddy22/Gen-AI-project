import React from 'react'

export default class ErrorBoundary extends React.Component {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="error-boundary" role="alert">
          <section className="error-boundary-panel">
            <h1>NoteBot couldn’t load this view.</h1>
            <p>Reload the page to try again.</p>
            <button type="button" className="btn-primary" onClick={() => window.location.reload()}>Reload</button>
          </section>
        </main>
      )
    }

    return this.props.children
  }
}