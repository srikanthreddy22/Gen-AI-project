import React from 'react'

export default function NotFoundPage() {
  return (
    <main className="not-found-page" aria-labelledby="not-found-title">
      <p className="not-found-code">404</p>
      <h1 id="not-found-title">This page isn’t here.</h1>
      <a className="btn-primary" href="/">Back to Workspace</a>
    </main>
  )
}